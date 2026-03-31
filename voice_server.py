"""FastAPI WebSocket server for Gemini Live API voice streaming.

Runs alongside Streamlit. Bridges browser audio <-> Gemini Live API
via the google-genai SDK for bidirectional voice conversations.
"""

import asyncio
import base64
import json
import os
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini model for Live API
GEMINI_LIVE_MODEL = "gemini-2.5-flash-preview-native-audio-dialog"

INTERVIEWER_SYSTEM_PROMPT = """You are a friendly, professional post-meeting debrief interviewer for a sales team. Your job is to conduct a brief voice conversation to capture what happened in a client meeting.

Your approach:
1. Start by asking how the meeting went overall
2. Ask focused follow-up questions based on the pre-meeting objectives provided in the meeting context
3. Probe for specifics: client reactions, objections, next steps, any surprises
4. Ask about deal status changes, timeline, and action items
5. Keep the conversation natural and conversational - this is a quick debrief, not an interrogation
6. After 5-8 exchanges, wrap up by summarizing what you heard and confirming accuracy

Important guidelines:
- Be concise in your questions - one question at a time
- Listen actively and reference what the salesperson just said
- If they mention something important, dig deeper
- Pay special attention to whether the pre-meeting KEY OBJECTIVES were addressed
- Keep a warm, supportive tone - you're helping them capture value, not evaluating them
"""

# Store active session transcripts keyed by session_id
_transcripts: dict[str, list[dict]] = {}


def _get_client() -> genai.Client:
    """Create a Gemini client using available API key."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        # Try loading from streamlit secrets toml directly
        import tomllib
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
                api_key = secrets.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment or .streamlit/secrets.toml")
    return genai.Client(api_key=api_key)


@app.websocket("/ws/voice/{session_id}")
async def voice_stream(websocket: WebSocket, session_id: str):
    """Bidirectional voice streaming endpoint.

    Protocol (JSON messages over WebSocket):
    - Client sends: {"type": "config", "meeting_context": "..."}  (first message)
    - Client sends: {"type": "audio", "data": "<base64 PCM16 16kHz>"}
    - Client sends: {"type": "end"}
    - Server sends: {"type": "audio", "data": "<base64 PCM16 24kHz>"}
    - Server sends: {"type": "transcript", "role": "user"|"assistant", "text": "...", "finished": bool}
    - Server sends: {"type": "turn_complete"}
    - Server sends: {"type": "error", "message": "..."}
    """
    await websocket.accept()
    _transcripts[session_id] = []

    try:
        # 1. Wait for config message with meeting context
        config_msg = await websocket.receive_json()
        if config_msg.get("type") != "config":
            await websocket.send_json({"type": "error", "message": "First message must be type 'config'"})
            await websocket.close()
            return

        meeting_context = config_msg.get("meeting_context", "")
        system_instruction = f"{INTERVIEWER_SYSTEM_PROMPT}\n\nMeeting Context:\n{meeting_context}"

        # 2. Connect to Gemini Live API
        client = _get_client()

        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore"
                    )
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text=system_instruction)]
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        async with client.aio.live.connect(
            model=GEMINI_LIVE_MODEL, config=live_config
        ) as gemini_session:

            # Signal ready to client
            await websocket.send_json({"type": "ready"})

            # Track partial transcripts
            current_user_text = ""
            current_agent_text = ""

            async def receive_from_gemini():
                """Read events from Gemini and forward audio + transcripts to browser."""
                nonlocal current_user_text, current_agent_text
                try:
                    async for response in gemini_session.receive():
                        sc = response.server_content
                        if sc is None:
                            continue

                        # Audio output
                        if sc.model_turn and sc.model_turn.parts:
                            for part in sc.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    audio_b64 = base64.b64encode(
                                        part.inline_data.data
                                    ).decode("ascii")
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": audio_b64,
                                    })

                        # Input transcription (what user said)
                        if sc.input_transcription and sc.input_transcription.text:
                            current_user_text += sc.input_transcription.text
                            finished = getattr(sc.input_transcription, "finished", False)
                            await websocket.send_json({
                                "type": "transcript",
                                "role": "user",
                                "text": sc.input_transcription.text,
                                "finished": finished,
                            })
                            if finished and current_user_text.strip():
                                _transcripts[session_id].append({
                                    "role": "user",
                                    "content": current_user_text.strip(),
                                })
                                current_user_text = ""

                        # Output transcription (what agent said)
                        if sc.output_transcription and sc.output_transcription.text:
                            current_agent_text += sc.output_transcription.text
                            finished = getattr(sc.output_transcription, "finished", False)
                            await websocket.send_json({
                                "type": "transcript",
                                "role": "assistant",
                                "text": sc.output_transcription.text,
                                "finished": finished,
                            })
                            if finished and current_agent_text.strip():
                                _transcripts[session_id].append({
                                    "role": "assistant",
                                    "content": current_agent_text.strip(),
                                })
                                current_agent_text = ""

                        # Turn complete
                        if sc.turn_complete:
                            # Flush any remaining agent text
                            if current_agent_text.strip():
                                _transcripts[session_id].append({
                                    "role": "assistant",
                                    "content": current_agent_text.strip(),
                                })
                                current_agent_text = ""
                            await websocket.send_json({"type": "turn_complete"})

                        # Interrupted (barge-in)
                        if sc.interrupted:
                            # Flush partial agent text
                            if current_agent_text.strip():
                                _transcripts[session_id].append({
                                    "role": "assistant",
                                    "content": current_agent_text.strip(),
                                })
                                current_agent_text = ""
                            await websocket.send_json({"type": "interrupted"})

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.exception("Error receiving from Gemini")
                    try:
                        await websocket.send_json({"type": "error", "message": str(e)})
                    except Exception:
                        pass

            # Start receiving from Gemini in background
            gemini_task = asyncio.create_task(receive_from_gemini())

            try:
                # 3. Forward audio from browser to Gemini
                while True:
                    msg = await websocket.receive_json()
                    msg_type = msg.get("type")

                    if msg_type == "audio":
                        audio_bytes = base64.b64decode(msg["data"])
                        await gemini_session.send_realtime_input(
                            audio=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                    elif msg_type == "end":
                        # Flush any remaining user text
                        if current_user_text.strip():
                            _transcripts[session_id].append({
                                "role": "user",
                                "content": current_user_text.strip(),
                            })
                            current_user_text = ""
                        break

            except WebSocketDisconnect:
                pass
            finally:
                gemini_task.cancel()
                try:
                    await gemini_task
                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Voice stream error")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@app.get("/api/transcript/{session_id}")
async def get_transcript(session_id: str):
    """Retrieve the accumulated transcript for a session."""
    transcript = _transcripts.get(session_id, [])
    return {"session_id": session_id, "transcript": transcript, "count": len(transcript)}


@app.delete("/api/transcript/{session_id}")
async def clear_transcript(session_id: str):
    """Clear transcript data for a session."""
    _transcripts.pop(session_id, None)
    return {"status": "ok"}
