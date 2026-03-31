"""Interview page - voice-based post-meeting debrief with Claude."""

import streamlit as st
from streamlit_mic_recorder import mic_recorder
from mock_data import get_meeting, update_meeting_status
from agent import (
    get_interview_response,
    get_opening_question,
    generate_summary,
    is_interview_complete,
    transcribe_audio,
    text_to_speech,
)
from utils import save_interview

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
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False
if "current_summary" not in st.session_state:
    st.session_state.current_summary = None
if "generating_summary" not in st.session_state:
    st.session_state.generating_summary = False
if "latest_audio_response" not in st.session_state:
    st.session_state.latest_audio_response = None
if "mic_key_counter" not in st.session_state:
    st.session_state.mic_key_counter = 0
if "last_transcription" not in st.session_state:
    st.session_state.last_transcription = None

# --- Header (stacked for mobile) ---
if st.button("< Dashboard", use_container_width=False):
    st.switch_page("pages/dashboard.py")
st.subheader(f"{meeting['client_name']} - {meeting['type']}")
st.caption(f"{meeting['date']}  |  {meeting['deal_name']}  |  {meeting['deal_stage']}")

st.divider()

# --- Start the interview (get opening question from Claude) ---
if not st.session_state.interview_started:
    with st.spinner("Starting interview..."):
        opening = get_opening_question(meeting)
        st.session_state.conversation_history = [
            {"role": "user", "content": "Hi, I just finished the meeting. Ready to debrief."},
            {"role": "assistant", "content": opening},
        ]
        # Generate TTS for the opening question
        try:
            st.session_state.latest_audio_response = text_to_speech(opening)
        except Exception:
            st.session_state.latest_audio_response = None
        st.session_state.interview_started = True
        st.rerun()

# --- Display conversation history ---
for msg in st.session_state.conversation_history:
    if msg["role"] == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.write(msg["content"])
    elif msg["role"] == "user":
        # Skip the initial "ready to debrief" message in display
        if msg["content"] == "Hi, I just finished the meeting. Ready to debrief.":
            continue
        with st.chat_message("user", avatar="👤"):
            st.write(msg["content"])

# --- Play latest agent audio response ---
if st.session_state.latest_audio_response:
    st.audio(st.session_state.latest_audio_response, format="audio/mp3", autoplay=True)

# --- Interview complete: show summary button ---
if st.session_state.interview_complete:
    st.success("Interview complete! Generating summary...")
    if not st.session_state.current_summary and not st.session_state.generating_summary:
        st.session_state.generating_summary = True
        st.rerun()

    if st.session_state.generating_summary and not st.session_state.current_summary:
        with st.spinner("Claude is summarizing your debrief..."):
            summary = generate_summary(
                st.session_state.conversation_history, meeting
            )
            st.session_state.current_summary = summary
            st.session_state.generating_summary = False

            # Save to mock data and file
            update_meeting_status(
                meeting["id"], "complete",
                transcript=st.session_state.conversation_history,
                summary=summary,
            )
            save_interview(
                meeting["id"],
                st.session_state.conversation_history,
                summary,
            )
            st.rerun()

    if st.session_state.current_summary:
        st.session_state.active_meeting_id = meeting["id"]
        if st.button("View Summary", type="primary", use_container_width=True):
            st.switch_page("pages/summary.py")
    st.stop()

# --- Voice recording ---
st.markdown("---")
st.markdown("**Tap the mic to record your response:**")

# Dynamic key so the recorder resets after each turn
audio = mic_recorder(
    start_prompt="🎤 Start Recording",
    stop_prompt="⏹️ Stop Recording",
    just_once=False,
    use_container_width=True,
    key=f"mic_{st.session_state.mic_key_counter}",
)

# Show last transcription result
if st.session_state.last_transcription:
    st.caption(f"📝 You said: *\"{st.session_state.last_transcription}\"*")

# --- Process recorded audio ---
transcript_text = None
if audio and audio["bytes"]:
    with st.spinner("Transcribing your response..."):
        try:
            transcript_text = transcribe_audio(audio["bytes"])
            if transcript_text:
                st.session_state.last_transcription = transcript_text
        except Exception as e:
            st.error(f"Transcription failed: {e}")

# --- Text input fallback ---
text_input = st.chat_input("Or type your response here...")
if text_input:
    transcript_text = text_input

# --- Handle new user input ---
if transcript_text:
    # Add user message to history
    st.session_state.conversation_history.append(
        {"role": "user", "content": transcript_text}
    )

    # Get Claude's response
    with st.spinner("Thinking..."):
        response = get_interview_response(
            st.session_state.conversation_history, meeting
        )

    # Add assistant message to history
    st.session_state.conversation_history.append(
        {"role": "assistant", "content": response}
    )

    # Generate TTS for the response
    try:
        st.session_state.latest_audio_response = text_to_speech(response)
    except Exception:
        st.session_state.latest_audio_response = None

    # Reset mic for next turn
    st.session_state.mic_key_counter += 1
    st.session_state.last_transcription = transcript_text

    # Check if interview is complete
    if is_interview_complete(response):
        st.session_state.interview_complete = True

    st.rerun()

# --- Manual end interview button ---
st.markdown("---")
if st.button("End Interview & Generate Summary", use_container_width=True):
    st.session_state.interview_complete = True
    st.rerun()
