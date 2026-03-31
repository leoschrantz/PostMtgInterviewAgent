"""Interview page - Gemini Live API voice agent for post-meeting debrief."""

import json
import streamlit as st
import requests
from mock_data import get_meeting, update_meeting_status
from agent import generate_summary
from utils import save_interview

VOICE_SERVER_URL = "ws://localhost:8001/ws/voice"
TRANSCRIPT_API_URL = "http://localhost:8001/api/transcript"

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
if "fetching_transcript" not in st.session_state:
    st.session_state.fetching_transcript = False
if "show_recap_form" not in st.session_state:
    st.session_state.show_recap_form = False
if "voice_session_id" not in st.session_state:
    import uuid
    st.session_state.voice_session_id = str(uuid.uuid4())

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

# --- Summary complete ---
if st.session_state.interview_complete and st.session_state.current_summary:
    st.success("Interview complete! Summary generated.")
    if st.button("View Summary", type="primary", use_container_width=True):
        st.switch_page("pages/summary.py")
    st.stop()

# --- Transcript fetch + summary generation ---
if st.session_state.fetching_transcript:
    with st.spinner("Fetching conversation transcript..."):
        try:
            session_id = st.session_state.voice_session_id
            resp = requests.get(f"{TRANSCRIPT_API_URL}/{session_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            transcript = data.get("transcript", [])

            if transcript:
                st.success(f"Transcript retrieved! ({len(transcript)} messages)")
                with st.spinner("Claude is generating your structured summary..."):
                    summary = generate_summary(transcript, meeting)
                    st.session_state.current_summary = summary
                    st.session_state.interview_complete = True

                    update_meeting_status(
                        meeting["id"], "complete",
                        transcript=transcript,
                        summary=summary,
                    )
                    save_interview(meeting["id"], transcript, summary)

                    # Clean up transcript from voice server
                    try:
                        requests.delete(f"{TRANSCRIPT_API_URL}/{session_id}", timeout=5)
                    except Exception:
                        pass

                    # Generate new session ID for next interview
                    import uuid
                    st.session_state.voice_session_id = str(uuid.uuid4())
                    st.rerun()
            else:
                st.warning("Transcript is empty. Make sure you've completed a conversation first.")
                st.session_state.fetching_transcript = False
        except Exception as e:
            st.error(f"Error fetching transcript: {e}")
            st.session_state.fetching_transcript = False

    if not st.session_state.interview_complete:
        if st.button("Try Again", use_container_width=True):
            st.session_state.fetching_transcript = True
            st.rerun()
        st.markdown("---")
        st.caption("If the transcript keeps failing, you can write a quick recap instead:")
        if st.button("Write recap manually instead", use_container_width=True):
            st.session_state.fetching_transcript = False
            st.session_state.show_recap_form = True
            st.rerun()
    st.stop()

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

# --- Gemini Voice Agent Widget ---
st.markdown("### Step 1: Have your debrief conversation")
st.caption("Tap the microphone button to start. The AI interviewer will ask you about your meeting.")

voice_session_id = st.session_state.voice_session_id

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
    export default function({ parentElement, data }) {
        const container = parentElement.querySelector('#voice-container');
        if (!container || container.dataset.initialized === 'true') return;
        container.dataset.initialized = 'true';

        const statusEl = container.querySelector('#voice-status');
        const micBtn = container.querySelector('#mic-btn');
        const micIcon = container.querySelector('#mic-icon');
        const stopIcon = container.querySelector('#stop-icon');
        const indicator = container.querySelector('#audio-indicator');
        const transcriptEl = container.querySelector('#transcript-display');

        const wsUrl = data.ws_url + '/' + data.session_id;
        const meetingContext = data.meeting_context;

        let ws = null;
        let audioContext = null;
        let mediaStream = null;
        let workletNode = null;
        let isActive = false;

        // Audio playback queue
        let playbackQueue = [];
        let isPlaying = false;

        function setStatus(text) {
            statusEl.textContent = text;
        }

        function addTranscript(role, text, finished) {
            // Find or create the current partial element
            let partialId = 'partial-' + role;
            let el = container.querySelector('#' + partialId);
            if (!el) {
                el = document.createElement('div');
                el.id = partialId;
                el.className = role === 'user' ? 'user-msg' : 'agent-msg';
                let label = role === 'user' ? 'You' : 'Interviewer';
                el.innerHTML = '<span class="label">' + label + ':</span> ';
                transcriptEl.appendChild(el);
            }
            // Append text
            el.innerHTML += text;

            if (finished) {
                el.removeAttribute('id');
            }
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        }

        async function playAudioChunk(b64Data) {
            playbackQueue.push(b64Data);
            if (!isPlaying) {
                processPlaybackQueue();
            }
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

            // Play via AudioContext
            if (!audioContext) return;
            const buffer = audioContext.createBuffer(1, float32.length, 24000);
            buffer.getChannelData(0).set(float32);
            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);
            source.onended = () => processPlaybackQueue();
            source.start();
        }

        async function startConversation() {
            try {
                setStatus('Connecting...');

                // Init audio context
                audioContext = new AudioContext({ sampleRate: 16000 });

                // Get microphone
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
                });

                // Connect WebSocket
                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    // Send config as first message
                    ws.send(JSON.stringify({
                        type: 'config',
                        meeting_context: meetingContext,
                    }));
                };

                ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);

                    if (msg.type === 'ready') {
                        setStatus('Connected! Speak naturally...');
                        startMicCapture();
                    } else if (msg.type === 'audio') {
                        playAudioChunk(msg.data);
                        indicator.style.width = '80%';
                        setTimeout(() => { indicator.style.width = '0%'; }, 200);
                    } else if (msg.type === 'transcript') {
                        addTranscript(msg.role, msg.text, msg.finished);
                    } else if (msg.type === 'turn_complete') {
                        indicator.style.width = '0%';
                    } else if (msg.type === 'interrupted') {
                        // Clear playback queue on barge-in
                        playbackQueue = [];
                    } else if (msg.type === 'error') {
                        setStatus('Error: ' + msg.message);
                    }
                };

                ws.onerror = () => {
                    setStatus('Connection error. Is the voice server running?');
                };

                ws.onclose = () => {
                    if (isActive) {
                        setStatus('Connection closed.');
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
            if (!audioContext || !mediaStream || !ws) return;

            // Load AudioWorklet for mic capture
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
            const url = URL.createObjectURL(blob);
            await audioContext.audioWorklet.addModule(url);
            URL.revokeObjectURL(url);

            const source = audioContext.createMediaStreamSource(mediaStream);
            workletNode = new AudioWorkletNode(audioContext, 'mic-processor');

            workletNode.port.onmessage = (event) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    const pcmBytes = new Uint8Array(event.data);
                    let binary = '';
                    for (let i = 0; i < pcmBytes.length; i++) {
                        binary += String.fromCharCode(pcmBytes[i]);
                    }
                    const b64 = btoa(binary);
                    ws.send(JSON.stringify({ type: 'audio', data: b64 }));

                    // Visual feedback for mic input
                    indicator.style.width = '40%';
                    setTimeout(() => { indicator.style.width = '0%'; }, 100);
                }
            };

            source.connect(workletNode);
            workletNode.connect(audioContext.destination);
        }

        function stopConversation() {
            isActive = false;
            micBtn.classList.remove('active');
            micIcon.style.display = 'block';
            stopIcon.style.display = 'none';
            indicator.style.width = '0%';

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'end' }));
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
            setStatus('Conversation ended. Click below to generate your summary.');
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

_voice_widget(
    data={
        "ws_url": VOICE_SERVER_URL,
        "session_id": voice_session_id,
        "meeting_context": meeting_context,
    },
    key="gemini_voice",
    height=400,
)

# --- End interview ---
st.markdown("---")
st.markdown("### Step 2: End the call, then generate your summary")
st.caption("Stop the conversation above first, then click the button below.")

if st.button("End Interview & Generate Summary", type="primary", use_container_width=True):
    st.session_state.fetching_transcript = True
    st.rerun()
