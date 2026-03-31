"""Voice component wrapper using Streamlit v2 components API."""

import streamlit as st
from pathlib import Path

_component_dir = Path(__file__).parent

_voice_component = st.components.v2.component(
    "voice_interface",
    html=(_component_dir / "voice_component.html").read_text(),
    css=(_component_dir / "voice_component.css").read_text(),
    js=(_component_dir / "voice_component.js").read_text(),
)


def render_voice_interface(tts_text: str = "", tts_id: str = "", key: str = "voice"):
    """Render the voice interface component.

    Args:
        tts_text: Text for the agent to speak aloud via browser TTS.
        tts_id: Unique ID for this TTS utterance (prevents re-speaking on reruns).
        key: Streamlit component key.

    Returns:
        Component result with:
        - .transcript: User's speech-to-text (trigger, resets after rerun)
        - .is_recording: Whether the mic is currently active (state)
        - .tts_speaking: Whether TTS is currently playing (state)
        - .stt_supported: Whether the browser supports speech recognition (state)
    """
    def _noop():
        pass

    result = _voice_component(
        data={"tts_text": tts_text, "tts_id": tts_id},
        default={"is_recording": False, "tts_speaking": False, "stt_supported": True},
        key=key,
        height=120,
        on_is_recording_change=_noop,
        on_tts_speaking_change=_noop,
        on_stt_supported_change=_noop,
        on_transcript_change=_noop,
    )
    return result
