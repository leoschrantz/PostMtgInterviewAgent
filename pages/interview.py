"""Interview page - Gemini Live API voice agent for post-meeting debrief.

Architecture: Browser connects directly to Gemini's WebSocket endpoint.
No intermediary server needed — works on Streamlit Cloud.
"""

import json
import streamlit as st
from google import genai
from google.genai import types
import datetime
from mock_data import get_meeting, update_meeting_status
from agent import generate_summary
from utils import save_interview


GEMINI_LIVE_MODEL = "gemini-2.0-flash-live-001"

INTERVIEWER_SYSTEM_PROMPT = """You are a friendly, professional post-meeting debrief interviewer for a sales team. Your job is to conduct a brief voice conversation to capture what happened in a client meeting.

Your approach:
1. Start by greeting the salesperson warmly and asking how the meeting went overall
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
- Start immediately with a warm greeting and ask how the meeting went"""

# --- Guard: must have an active meeting ---
if "active_meeting_id" not in st.session_state or not st.session_state.active_meeting_id:
    st.warning("No meeting selected. Please go to the dashboard and select a meeting.")
    if st.button("Go to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

meeting = get_meeting(st.session_state.active_meeting_id)
if not meeting:
    st.error("Meeting not found.")
    st.stop()

# --- Initialize session state ---
if "current_summary" not in st.session_state:
    st.session_state.current_summary = None
if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False
if "show_recap_form" not in st.session_state:
    st.session_state.show_recap_form = False

# --- Header (stacked for mobile) ---
if st.button("< Dashboard", use_container_width=False):
    st.switch_page("pages/dashboard.py")
st.subheader(f"{meeting['client_name']} - {meeting['type']}")
st.caption(f"{meeting['date']}  |  {meeting['deal_name']}  |  {meeting['deal_stage']}")

st.divider()

# --- Build meeting context for the agent ---
meeting_context = (
    f"Client: {meeting['client_name']} ({meeting['client_contact']}). "
    f"Meeting type: {meeting['type']}. "
    f"Deal: {meeting['deal_name']} - {meeting['deal_stage']} - {meeting['deal_value']}. "
    f"Date: {meeting['date']} at {meeting['time']}. "
    f"Attendees: {', '.join(meeting['attendees'])}. "
    f"Pre-meeting notes: {meeting['notes_pre']}"
)

system_instruction = f"{INTERVIEWER_SYSTEM_PROMPT}\n\nMeeting Context:\n{meeting_context}"

# --- Generate ephemeral token for browser-to-Gemini connection ---
@st.cache_data(ttl=50)  # Cache for 50 seconds (token valid for 60s new sessions)
def _get_ephemeral_token():
    """Generate a short-lived token so the API key stays server-side."""
    client = genai.Client(
        api_key=st.secrets["GOOGLE_API_KEY"],
        http_options={"api_version": "v1alpha"},
    )
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    token = client.auth_tokens.create(
        config={
            "uses": 1,
            "expire_time": now + datetime.timedelta(minutes=30),
            "new_session_expire_time": now + datetime.timedelta(minutes=2),
            "http_options": {"api_version": "v1alpha"},
        }
    )
    return token.name

# --- Summary complete ---
if st.session_state.interview_complete and st.session_state.current_summary:
    st.success("Interview complete! Summary generated.")
    if st.button("View Summary", type="primary", use_container_width=True):
        st.switch_page("pages/summary.py")
    st.stop()

# --- Summary generation from transcript ---
if "pending_transcript" in st.session_state and st.session_state.pending_transcript:
    transcript = st.session_state.pending_transcript
    st.session_state.pending_transcript = None
    with st.spinner(f"Transcript captured ({len(transcript)} messages). Claude is generating your summary..."):
        try:
            summary = generate_summary(transcript, meeting)
            st.session_state.current_summary = summary
            st.session_state.interview_complete = True
            update_meeting_status(
                meeting["id"], "complete",
                transcript=transcript,
                summary=summary,
            )
            save_interview(meeting["id"], transcript, summary)
            st.rerun()
        except Exception as e:
            st.error(f"Error generating summary: {e}")
            st.session_state.show_recap_form = True

# --- Manual recap fallback ---
if st.session_state.show_recap_form:
    st.markdown("### Quick Recap")
    st.markdown("Jot down the key points from your conversation so we can generate a structured summary.")

    recap_text = st.text_area(
        "What did you cover in the debrief?",
        height=200,
        placeholder=(
            "Example:\n"
            "- Meeting went well, client was engaged\n"
            "- Discussed Velocity AI module, they were very interested\n"
            "- Didn't get to CloudSync Pro, need to follow up\n"
            "- Next steps: send proposal by Friday\n"
            "- Deal stage should move to Proposal"
        ),
    )

    if st.button("Generate Summary", type="primary", use_container_width=True):
        if recap_text.strip():
            with st.spinner("Claude is generating your structured summary..."):
                transcript = [
                    {"role": "user", "content": f"Here is my post-meeting debrief recap:\n\n{recap_text}"},
                ]
                try:
                    summary = generate_summary(transcript, meeting)
                    st.session_state.current_summary = summary
                    st.session_state.interview_complete = True
                    update_meeting_status(
                        meeting["id"], "complete",
                        transcript=transcript,
                        summary=summary,
                    )
                    save_interview(meeting["id"], transcript, summary)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating summary: {e}")
        else:
            st.warning("Please enter some notes first.")
    st.stop()

# --- Get ephemeral token ---
try:
    ephemeral_token = _get_ephemeral_token()
except Exception as e:
    st.error(f"Failed to connect to Google AI: {e}")
    st.caption("Check that GOOGLE_API_KEY is set correctly in Streamlit secrets.")
    st.session_state.show_recap_form = True
    st.stop()

# --- Gemini Voice Agent Widget ---
st.markdown("### Step 1: Have your debrief conversation")
st.caption("Tap the microphone button to start. The AI interviewer will ask you about your meeting.")

_voice_widget = st.components.v2.component(
    "gemini_voice_widget",
    html="""
    <div id="voice-container">
        <div id="voice-status">Tap the microphone to start your debrief</div>
        <div id="voice-controls">
            <button id="mic-btn" title="Start conversation">
                <svg id="mic-icon" viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
                <svg id="stop-icon" viewBox="0 0 24 24" width="32" height="32" fill="currentColor" style="display:none">
                    <rect x="6" y="6" width="12" height="12" rx="2"/>
                </svg>
            </button>
        </div>
        <div id="voice-visual">
            <div id="audio-indicator"></div>
        </div>
        <div id="transcript-display"></div>
    </div>
    <style>
        #voice-container {
            text-align: center;
            padding: 20px 10px;
            font-family: Arial, sans-serif;
        }
        #voice-status {
            font-size: 14px;
            color: #666;
            margin-bottom: 16px;
            min-height: 20px;
        }
        #voice-controls {
            margin-bottom: 16px;
        }
        #mic-btn {
            width: 72px;
            height: 72px;
            border-radius: 50%;
            border: 3px solid #000;
            background: #fff;
            color: #000;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }
        #mic-btn:hover {
            background: #f5f5f5;
        }
        #mic-btn.active {
            background: #000;
            color: #FFCE00;
            border-color: #FFCE00;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(255, 206, 0, 0.4); }
            50% { box-shadow: 0 0 0 12px rgba(255, 206, 0, 0); }
        }
        #audio-indicator {
            height: 4px;
            background: #FFCE00;
            border-radius: 2px;
            width: 0%;
            margin: 0 auto;
            max-width: 200px;
            transition: width 0.1s ease;
        }
        #voice-visual {
            min-height: 8px;
            margin-bottom: 12px;
        }
        #transcript-display {
            text-align: left;
            max-height: 200px;
            overflow-y: auto;
            font-size: 13px;
            line-height: 1.5;
            padding: 0 8px;
        }
        #transcript-display .user-msg {
            color: #333;
            margin: 4px 0;
        }
        #transcript-display .agent-msg {
            color: #008B5C;
            margin: 4px 0;
        }
        #transcript-display .label {
            font-weight: bold;
        }
    </style>
    """,
    js="""
    export default function(component) {
        const { setStateValue, parentElement, data } = component;
        const container = parentElement.querySelector('#voice-container');
        if (!container || container.dataset.initialized === 'true') return;
        container.dataset.initialized = 'true';

        const statusEl = container.querySelector('#voice-status');
        const micBtn = container.querySelector('#mic-btn');
        const micIcon = container.querySelector('#mic-icon');
        const stopIcon = container.querySelector('#stop-icon');
        const indicator = container.querySelector('#audio-indicator');
        const transcriptEl = container.querySelector('#transcript-display');

        const token = data.token;
        const model = data.model;
        const systemInstruction = data.system_instruction;

        // Gemini Live API WebSocket URL (using ephemeral token)
        const wsUrl = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?access_token=' + token;

        let ws = null;
        let audioContext = null;
        let playbackContext = null;
        let mediaStream = null;
        let workletNode = null;
        let isActive = false;
        let configSent = false;

        // Transcript accumulation
        let transcript = [];
        let currentUserText = '';
        let currentAgentText = '';

        // Audio playback queue
        let playbackQueue = [];
        let isPlaying = false;

        function setStatus(text) {
            statusEl.textContent = text;
        }

        function addTranscriptDisplay(role, text) {
            const el = document.createElement('div');
            el.className = role === 'user' ? 'user-msg' : 'agent-msg';
            const label = role === 'user' ? 'You' : 'Interviewer';
            el.innerHTML = '<span class="label">' + label + ':</span> ' + text;
            transcriptEl.appendChild(el);
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        }

        function flushUserText() {
            if (currentUserText.trim()) {
                transcript.push({ role: 'user', content: currentUserText.trim() });
                addTranscriptDisplay('user', currentUserText.trim());
                currentUserText = '';
            }
        }

        function flushAgentText() {
            if (currentAgentText.trim()) {
                transcript.push({ role: 'assistant', content: currentAgentText.trim() });
                addTranscriptDisplay('assistant', currentAgentText.trim());
                currentAgentText = '';
            }
        }

        async function playAudioChunk(b64Data) {
            playbackQueue.push(b64Data);
            if (!isPlaying) processPlaybackQueue();
        }

        async function processPlaybackQueue() {
            if (playbackQueue.length === 0) {
                isPlaying = false;
                return;
            }
            isPlaying = true;
            const b64 = playbackQueue.shift();
            const raw = atob(b64);
            const bytes = new Uint8Array(raw.length);
            for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

            // Convert 16-bit PCM 24kHz to Float32
            const pcm16 = new Int16Array(bytes.buffer);
            const float32 = new Float32Array(pcm16.length);
            for (let i = 0; i < pcm16.length; i++) {
                float32[i] = pcm16[i] / 32768.0;
            }

            if (!playbackContext) {
                playbackContext = new AudioContext({ sampleRate: 24000 });
            }
            const buffer = playbackContext.createBuffer(1, float32.length, 24000);
            buffer.getChannelData(0).set(float32);
            const source = playbackContext.createBufferSource();
            source.buffer = buffer;
            source.connect(playbackContext.destination);
            source.onended = () => processPlaybackQueue();
            source.start();
        }

        async function startConversation() {
            try {
                setStatus('Requesting microphone...');
                configSent = false;

                // Get microphone
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
                });

                setStatus('Connecting to Gemini...');

                // Connect directly to Gemini Live API
                ws = new WebSocket(wsUrl);

                let connectTimeout = setTimeout(() => {
                    if (isActive && !configSent) {
                        setStatus('Connection timed out. Try again.');
                        stopConversation();
                    }
                }, 15000);

                ws.onopen = () => {
                    clearTimeout(connectTimeout);
                    // Send setup config as first message
                    const setupMsg = {
                        setup: {
                            model: 'models/' + model,
                            generationConfig: {
                                responseModalities: ['AUDIO'],
                                speechConfig: {
                                    voiceConfig: {
                                        prebuiltVoiceConfig: {
                                            voiceName: 'Kore'
                                        }
                                    }
                                }
                            },
                            systemInstruction: {
                                parts: [{ text: systemInstruction }]
                            },
                            inputAudioTranscription: {},
                            outputAudioTranscription: {}
                        }
                    };
                    ws.send(JSON.stringify(setupMsg));
                    configSent = true;
                    setStatus('Connected! Interviewer is starting...');
                    startMicCapture();
                };

                ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);

                    // Setup complete acknowledgment
                    if (msg.setupComplete) {
                        setStatus('Interviewer is speaking...');
                    }

                    const sc = msg.serverContent;
                    if (!sc) return;

                    // Audio from model
                    if (sc.modelTurn && sc.modelTurn.parts) {
                        for (const part of sc.modelTurn.parts) {
                            if (part.inlineData && part.inlineData.data) {
                                playAudioChunk(part.inlineData.data);
                                indicator.style.width = '80%';
                                setTimeout(() => { indicator.style.width = '0%'; }, 200);
                            }
                        }
                        setStatus('Interviewer is speaking...');
                    }

                    // Input transcription (user speech)
                    if (sc.inputTranscription && sc.inputTranscription.text) {
                        currentUserText += sc.inputTranscription.text;
                        if (sc.inputTranscription.finished) {
                            flushUserText();
                        }
                    }

                    // Output transcription (agent speech)
                    if (sc.outputTranscription && sc.outputTranscription.text) {
                        currentAgentText += sc.outputTranscription.text;
                        if (sc.outputTranscription.finished) {
                            flushAgentText();
                        }
                    }

                    // Turn complete
                    if (sc.turnComplete) {
                        flushAgentText();
                        indicator.style.width = '0%';
                        setStatus('Your turn \u2014 speak when ready');
                    }

                    // Interrupted (barge-in)
                    if (sc.interrupted) {
                        flushAgentText();
                        playbackQueue = [];
                        isPlaying = false;
                        setStatus('Listening...');
                    }
                };

                ws.onerror = (err) => {
                    clearTimeout(connectTimeout);
                    console.error('WebSocket error:', err);
                    setStatus('Connection error. Check console for details.');
                };

                ws.onclose = (event) => {
                    clearTimeout(connectTimeout);
                    if (isActive) {
                        const reason = event.reason || (event.code === 1000 ? '' : 'code ' + event.code);
                        setStatus('Connection closed' + (reason ? ': ' + reason : '') + '. Tap mic to reconnect.');
                        stopConversation();
                    }
                };

                isActive = true;
                micBtn.classList.add('active');
                micIcon.style.display = 'none';
                stopIcon.style.display = 'block';

            } catch (err) {
                setStatus('Error: ' + err.message);
                console.error('Start error:', err);
            }
        }

        async function startMicCapture() {
            if (!mediaStream) return;

            // Create a separate audio context for mic capture at 16kHz
            audioContext = new AudioContext({ sampleRate: 16000 });

            const workletCode = `
                class MicProcessor extends AudioWorkletProcessor {
                    process(inputs) {
                        const input = inputs[0];
                        if (input.length > 0) {
                            const samples = input[0];
                            const pcm16 = new Int16Array(samples.length);
                            for (let i = 0; i < samples.length; i++) {
                                const s = Math.max(-1, Math.min(1, samples[i]));
                                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
                        }
                        return true;
                    }
                }
                registerProcessor('mic-processor', MicProcessor);
            `;
            const blob = new Blob([workletCode], { type: 'application/javascript' });
            const blobUrl = URL.createObjectURL(blob);
            await audioContext.audioWorklet.addModule(blobUrl);
            URL.revokeObjectURL(blobUrl);

            const source = audioContext.createMediaStreamSource(mediaStream);
            workletNode = new AudioWorkletNode(audioContext, 'mic-processor');

            workletNode.port.onmessage = (event) => {
                if (ws && ws.readyState === WebSocket.OPEN && configSent) {
                    const pcmBytes = new Uint8Array(event.data);
                    let binary = '';
                    for (let i = 0; i < pcmBytes.length; i++) {
                        binary += String.fromCharCode(pcmBytes[i]);
                    }
                    const b64 = btoa(binary);
                    ws.send(JSON.stringify({
                        realtimeInput: {
                            audio: {
                                data: b64,
                                mimeType: 'audio/pcm;rate=16000'
                            }
                        }
                    }));
                    indicator.style.width = '40%';
                    setTimeout(() => { indicator.style.width = '0%'; }, 100);
                }
            };

            source.connect(workletNode);
            // Don't connect to destination - we don't want mic feedback
            workletNode.connect(audioContext.createMediaStreamDestination());
        }

        function stopConversation() {
            isActive = false;
            micBtn.classList.remove('active');
            micIcon.style.display = 'block';
            stopIcon.style.display = 'none';
            indicator.style.width = '0%';

            // Flush any remaining text
            flushUserText();
            flushAgentText();

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
            ws = null;

            if (workletNode) {
                workletNode.disconnect();
                workletNode = null;
            }
            if (mediaStream) {
                mediaStream.getTracks().forEach(t => t.stop());
                mediaStream = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }

            playbackQueue = [];
            isPlaying = false;

            // Send transcript back to Streamlit via setStateValue
            if (transcript.length > 0) {
                setStateValue('transcript', JSON.stringify(transcript));
                setStatus('Conversation ended (' + transcript.length + ' messages captured). Click below to generate summary.');
            } else {
                setStatus('Conversation ended. No transcript captured. Try the manual recap below.');
            }
        }

        micBtn.addEventListener('click', () => {
            if (isActive) {
                stopConversation();
            } else {
                startConversation();
            }
        });
    }
    """,
    isolate_styles=False,
)

widget_result = _voice_widget(
    data={
        "token": ephemeral_token,
        "model": GEMINI_LIVE_MODEL,
        "system_instruction": system_instruction,
    },
    default={"transcript": ""},
    key="gemini_voice",
    height=400,
)

# --- End interview ---
st.markdown("---")
st.markdown("### Step 2: End the call, then generate your summary")
st.caption("Stop the conversation above first, then click the button below.")

if st.button("End Interview & Generate Summary", type="primary", use_container_width=True):
    # Read transcript from widget state
    raw = widget_result.transcript if widget_result else ""
    if raw:
        try:
            transcript = json.loads(raw)
            if transcript:
                st.session_state.pending_transcript = transcript
                st.rerun()
            else:
                st.warning("Transcript is empty. Make sure you've had a conversation first.")
        except json.JSONDecodeError:
            st.error("Failed to parse transcript data.")
    else:
        st.warning("No transcript captured yet. Have a conversation first, or use the manual recap below.")

    st.session_state.show_recap_form = True
    st.rerun()
