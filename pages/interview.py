"""Interview page - Gemini Live API voice agent for post-meeting debrief.

Architecture: Browser connects directly to Gemini's WebSocket endpoint.
No intermediary server needed — works on Streamlit Cloud.
"""

import json
import streamlit as st
from mock_data import get_meeting, update_meeting_status
from agent import generate_summary
from utils import save_interview


GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"

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

# --- API key for browser-to-Gemini connection ---
# For production, use ephemeral tokens instead. For this prototype,
# the API key is passed to the browser for direct WebSocket connection.
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

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

if not GOOGLE_API_KEY:
    st.error("GOOGLE_API_KEY not found in Streamlit secrets.")
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

        const apiKey = data.api_key;
        const model = data.model;
        const systemInstruction = data.system_instruction;

        // Clean up any previous connection (guards against double-init from Streamlit reruns)
        if (window._geminiWs && window._geminiWs.readyState <= WebSocket.OPEN) {
            console.log('[Voice] Closing stale WebSocket from previous render');
            window._geminiWs.onclose = null;
            window._geminiWs.close();
        }

        // Gemini Live API WebSocket URL
        const wsUrl = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=' + apiKey;

        let ws = null;
        let audioContext = null;
        let playbackContext = null;
        let mediaStream = null;
        let workletNode = null;
        let isActive = false;
        let configSent = false;
        let setupComplete = false;  // true once Gemini acknowledges config

        // Transcript accumulation
        let transcript = [];
        let currentUserText = '';
        let currentAgentText = '';

        // Audio playback scheduling
        let nextPlayTime = 0;

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

        // Live streaming display elements (updated as text arrives)
        let liveUserEl = null;
        let liveAgentEl = null;

        function updateLiveText(role, fullText) {
            const isUser = role === 'user';
            let el = isUser ? liveUserEl : liveAgentEl;
            if (!el) {
                el = document.createElement('div');
                el.className = (isUser ? 'user-msg' : 'agent-msg') + ' live';
                el.style.opacity = '0.7';
                const label = isUser ? 'You' : 'Interviewer';
                el.innerHTML = '<span class="label">' + label + ':</span> <span class="live-text"></span>';
                transcriptEl.appendChild(el);
                if (isUser) { liveUserEl = el; } else { liveAgentEl = el; }
            }
            el.querySelector('.live-text').textContent = fullText;
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        }

        function finalizeLive(role) {
            const isUser = role === 'user';
            const el = isUser ? liveUserEl : liveAgentEl;
            if (el) {
                el.style.opacity = '1';
                el.classList.remove('live');
                if (isUser) { liveUserEl = null; } else { liveAgentEl = null; }
            }
        }

        function flushUserText() {
            if (currentUserText.trim()) {
                transcript.push({ role: 'user', content: currentUserText.trim() });
                finalizeLive('user');
                currentUserText = '';
            } else if (liveUserEl) {
                // No text accumulated but live el exists — remove it
                liveUserEl.remove();
                liveUserEl = null;
            }
        }

        function flushAgentText() {
            if (currentAgentText.trim()) {
                transcript.push({ role: 'assistant', content: currentAgentText.trim() });
                finalizeLive('assistant');
                currentAgentText = '';
            } else if (liveAgentEl) {
                liveAgentEl.remove();
                liveAgentEl = null;
            }
        }

        let audioChunkCount = 0;
        let activeSources = [];  // Track scheduled audio sources for cancellation

        function stopAllPlayback() {
            for (const src of activeSources) {
                try { src.stop(); } catch (e) { /* already stopped */ }
            }
            activeSources = [];
            nextPlayTime = 0;
        }

        function playAudioChunk(b64Data) {
            if (!playbackContext) { console.warn('[Voice] No playbackContext'); return; }
            if (playbackContext.state === 'suspended') {
                playbackContext.resume();
            }
            audioChunkCount++;
            if (audioChunkCount <= 3) {
                console.log('[Voice] Audio chunk #' + audioChunkCount + ': ' + b64Data.length + ' b64 chars, ctx state=' + playbackContext.state);
            }

            // Decode base64 to bytes properly
            const binaryStr = atob(b64Data);
            const len = binaryStr.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryStr.charCodeAt(i);
            }

            // Convert bytes to Int16 samples (16-bit PCM, little-endian)
            const sampleCount = Math.floor(bytes.length / 2);
            if (sampleCount === 0) return;

            const float32 = new Float32Array(sampleCount);
            for (let i = 0; i < sampleCount; i++) {
                // Read little-endian int16
                let sample = bytes[i * 2] | (bytes[i * 2 + 1] << 8);
                if (sample >= 0x8000) sample -= 0x10000;
                float32[i] = sample / 32768.0;
            }

            // Create audio buffer at 24kHz
            const buffer = playbackContext.createBuffer(1, float32.length, 24000);
            buffer.getChannelData(0).set(float32);

            const source = playbackContext.createBufferSource();
            source.buffer = buffer;
            source.connect(playbackContext.destination);

            // Clean up reference when source finishes naturally
            source.onended = () => {
                const idx = activeSources.indexOf(source);
                if (idx !== -1) activeSources.splice(idx, 1);
            };

            // Schedule for gapless playback
            const now = playbackContext.currentTime;
            if (nextPlayTime < now) {
                nextPlayTime = now;
            }
            source.start(nextPlayTime);
            nextPlayTime += buffer.duration;
            activeSources.push(source);
        }

        async function startConversation() {
            try {
                setStatus('Requesting microphone...');
                configSent = false;
                setupComplete = false;

                // Create playback AudioContext during user gesture (required by browsers)
                if (!playbackContext) {
                    playbackContext = new AudioContext({ sampleRate: 24000 });
                }
                // Chrome suspends AudioContext until resumed during user gesture
                if (playbackContext.state === 'suspended') {
                    await playbackContext.resume();
                }
                console.log('[Voice] playbackContext state:', playbackContext.state, 'sampleRate:', playbackContext.sampleRate);

                // Get microphone
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
                });

                setStatus('Connecting to Gemini...');

                // Connect directly to Gemini Live API
                ws = new WebSocket(wsUrl);
                window._geminiWs = ws;  // Track globally for cleanup

                let connectTimeout = setTimeout(() => {
                    if (isActive && !configSent) {
                        setStatus('Connection timed out. Try again.');
                        stopConversation();
                    }
                }, 15000);

                ws.onopen = () => {
                    clearTimeout(connectTimeout);
                    // Send setup as first message (must be sent before anything else)
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
                    setStatus('Connected! Waiting for setup...');
                    // NOTE: Do NOT start mic capture here — wait for setupComplete
                };

                let msgCount = 0;
                ws.onmessage = async (event) => {
                    msgCount++;

                    // Gemini may send binary Blob frames — read as text for JSON parsing
                    let rawText;
                    if (event.data instanceof Blob) {
                        rawText = await event.data.text();
                    } else {
                        rawText = event.data;
                    }

                    let msg;
                    try {
                        msg = JSON.parse(rawText);
                    } catch (e) {
                        console.warn('[Voice] Non-JSON message, length:', rawText.length);
                        return;
                    }

                    if (msgCount <= 5) {
                        console.log('[Voice] JSON msg #' + msgCount + ':', JSON.stringify(msg).substring(0, 300));
                    }

                    // Setup complete acknowledgment
                    if (msg.setupComplete) {
                        setupComplete = true;
                        console.log('[Voice] Setup complete — sending greeting prompt');
                        setStatus('Interviewer is starting...');

                        // Use realtimeInput.text to prompt the greeting
                        // (clientContent caused "invalid argument" on v1beta)
                        ws.send(JSON.stringify({
                            realtimeInput: {
                                text: 'The salesperson just joined the debrief. Greet them warmly and ask how the meeting went overall. Keep it brief — one or two sentences.'
                            }
                        }));

                        // Start mic capture after a brief delay to let greeting process
                        setTimeout(() => { startMicCapture(); }, 300);
                    }

                    const sc = msg.serverContent;
                    if (!sc) return;

                    // Audio from model (inline base64 in JSON)
                    if (sc.modelTurn && sc.modelTurn.parts) {
                        // Agent is speaking — flush any pending user text as a completed turn
                        flushUserText();
                        for (const part of sc.modelTurn.parts) {
                            if (part.inlineData && part.inlineData.data) {
                                playAudioChunk(part.inlineData.data);
                                indicator.style.width = '80%';
                                setTimeout(() => { indicator.style.width = '0%'; }, 200);
                            }
                        }
                        setStatus('Interviewer is speaking...');
                    }

                    // Input transcription (user speech) — show live as it streams
                    if (sc.inputTranscription && sc.inputTranscription.text) {
                        // User is speaking — stop agent audio and flush agent text
                        if (activeSources.length > 0) { stopAllPlayback(); }
                        flushAgentText();
                        currentUserText += sc.inputTranscription.text;
                        updateLiveText('user', currentUserText.trim());
                        if (sc.inputTranscription.finished) {
                            flushUserText();
                        }
                    }

                    // Output transcription (agent speech) — show live as it streams
                    if (sc.outputTranscription && sc.outputTranscription.text) {
                        currentAgentText += sc.outputTranscription.text;
                        updateLiveText('assistant', currentAgentText.trim());
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

                    // Interrupted (barge-in) — stop all queued audio immediately
                    if (sc.interrupted) {
                        stopAllPlayback();
                        flushAgentText();
                        setStatus('Listening...');
                    }
                };

                ws.onerror = (err) => {
                    clearTimeout(connectTimeout);
                    console.error('WebSocket error:', err);
                    if (!setupComplete) {
                        setStatus('Failed to connect to Gemini. Check API key and try again.');
                    }
                };

                ws.onclose = (event) => {
                    clearTimeout(connectTimeout);
                    console.log('[Voice] WebSocket closed: code=' + event.code + ' reason=' + event.reason + ' setupComplete=' + setupComplete + ' msgCount=' + msgCount);
                    if (isActive) {
                        if (!setupComplete) {
                            setStatus('Gemini rejected connection (code ' + event.code + '). Check API key in Streamlit secrets.');
                            cleanup();
                        } else {
                            const reason = event.reason || '';
                            setStatus('Connection closed' + (reason ? ': ' + reason : '') + '. Tap mic to reconnect.');
                            cleanup();
                        }
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
                if (ws && ws.readyState === WebSocket.OPEN && setupComplete) {
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

        function cleanup() {
            // Release resources without setting status
            isActive = false;
            micBtn.classList.remove('active');
            micIcon.style.display = 'block';
            stopIcon.style.display = 'none';
            indicator.style.width = '0%';

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

            nextPlayTime = 0;
        }

        function stopConversation() {
            // Flush any remaining text
            flushUserText();
            flushAgentText();

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
            ws = null;

            cleanup();

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

def _on_transcript_change():
    """Called when the voice widget sends transcript data back."""
    pass

widget_result = _voice_widget(
    data={
        "api_key": GOOGLE_API_KEY,
        "model": GEMINI_LIVE_MODEL,
        "system_instruction": system_instruction,
    },
    default={"transcript": ""},
    key="gemini_voice",
    height=400,
    on_transcript_change=_on_transcript_change,
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
