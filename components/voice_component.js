export default function ({ parentElement, data, setStateValue, setTriggerValue }) {
    const micBtn = parentElement.querySelector("#mic-btn");
    const statusText = parentElement.querySelector("#status-text");
    const transcriptPreview = parentElement.querySelector("#transcript-preview");
    const unsupportedMsg = parentElement.querySelector("#unsupported-msg");

    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const supported = !!SpeechRecognition;
    setStateValue("stt_supported", supported);

    if (!supported) {
        micBtn.classList.add("disabled");
        unsupportedMsg.style.display = "block";
        statusText.textContent = "Not supported";
        return;
    }

    // Avoid re-initializing if already set up on this element
    if (micBtn.dataset.initialized === "true") {
        // Still handle TTS on reruns
        handleTTS(parentElement, data, setStateValue);
        return;
    }
    micBtn.dataset.initialized = "true";

    let recognition = null;
    let fullTranscript = "";
    let isRecording = false;
    let intentionalStop = false;

    function createRecognition() {
        const rec = new SpeechRecognition();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = "en-US";

        rec.onresult = (event) => {
            let interim = "";
            // Rebuild full transcript from all results
            let sessionTranscript = "";
            for (let i = 0; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    sessionTranscript += event.results[i][0].transcript;
                } else {
                    interim += event.results[i][0].transcript;
                }
            }
            // Combine any previous transcript (from auto-restarts) with current session
            const displayText = (fullTranscript + sessionTranscript + interim).trim();
            transcriptPreview.textContent = displayText || "";
            // Store the finalized portion for when we stop
            micBtn.dataset.currentSession = sessionTranscript;
        };

        rec.onerror = (event) => {
            console.warn("Speech recognition error:", event.error);
            // "no-speech" is normal - just means silence, don't stop
            if (event.error === "no-speech") return;
            if (event.error === "aborted") return;
            finishRecording();
        };

        rec.onend = () => {
            // Capture finalized text from this session
            const sessionText = micBtn.dataset.currentSession || "";
            if (sessionText) {
                fullTranscript += sessionText;
                micBtn.dataset.currentSession = "";
            }

            // If user hasn't clicked stop, auto-restart (handles browser timeout)
            if (isRecording && !intentionalStop) {
                try {
                    recognition = createRecognition();
                    recognition.start();
                } catch (e) {
                    console.warn("Could not restart recognition:", e);
                    finishRecording();
                }
                return;
            }

            // User clicked stop - finalize
            finishRecording();
        };

        return rec;
    }

    function startRecording() {
        if (isRecording) return;

        // Cancel any ongoing TTS so the mic can hear clearly
        window.speechSynthesis.cancel();

        isRecording = true;
        intentionalStop = false;
        fullTranscript = "";
        micBtn.dataset.currentSession = "";

        micBtn.classList.add("recording");
        statusText.textContent = "Recording... click mic to stop";
        statusText.classList.add("recording");
        transcriptPreview.textContent = "";
        setStateValue("is_recording", true);

        recognition = createRecognition();
        try {
            recognition.start();
        } catch (e) {
            console.warn("Could not start recognition:", e);
            finishRecording();
        }
    }

    function stopRecording() {
        if (!isRecording) return;
        intentionalStop = true;
        if (recognition) {
            try {
                recognition.stop();
            } catch (e) {
                finishRecording();
            }
        }
    }

    function finishRecording() {
        isRecording = false;
        intentionalStop = false;
        micBtn.classList.remove("recording");
        statusText.textContent = "Click mic to start recording";
        statusText.classList.remove("recording");
        setStateValue("is_recording", false);

        // Grab any remaining session text
        const sessionText = micBtn.dataset.currentSession || "";
        if (sessionText) {
            fullTranscript += sessionText;
            micBtn.dataset.currentSession = "";
        }

        const finalText = fullTranscript.trim();
        if (finalText) {
            transcriptPreview.textContent = finalText;
            setTriggerValue("transcript", finalText);
        }
        fullTranscript = "";
    }

    // Toggle: click to start, click again to stop
    micBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    // Handle TTS on initial load too
    handleTTS(parentElement, data, setStateValue);
}

function handleTTS(parentElement, data, setStateValue) {
    const micBtn = parentElement.querySelector("#mic-btn");

    if (!data || !data.tts_text) return;

    const ttsText = data.tts_text;
    const ttsId = data.tts_id || "";

    // Only speak if this is a new TTS request (identified by tts_id)
    if (micBtn.dataset.lastTtsId === ttsId) return;
    micBtn.dataset.lastTtsId = ttsId;

    // Cancel any previous speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(ttsText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    // Try to pick a natural-sounding voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(
        (v) => v.lang.startsWith("en") && v.name.toLowerCase().includes("natural")
    ) || voices.find(
        (v) => v.lang.startsWith("en-US")
    ) || voices.find(
        (v) => v.lang.startsWith("en")
    );
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => setStateValue("tts_speaking", true);
    utterance.onend = () => setStateValue("tts_speaking", false);
    utterance.onerror = () => setStateValue("tts_speaking", false);

    window.speechSynthesis.speak(utterance);
}
