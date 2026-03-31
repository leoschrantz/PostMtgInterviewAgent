"""Interview page - ElevenLabs conversational AI widget for post-meeting debrief."""

import json
import streamlit as st
from mock_data import get_meeting, update_meeting_status
from agent import generate_summary, get_latest_conversation_id, fetch_conversation_transcript
from utils import save_interview

AGENT_ID = "agent_7901kn0qbhyzem5ac63stkxkqtst"

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

# --- Header (stacked for mobile) ---
if st.button("< Dashboard", use_container_width=False):
    st.switch_page("pages/dashboard.py")
st.subheader(f"{meeting['client_name']} - {meeting['type']}")
st.caption(f"{meeting['date']}  |  {meeting['deal_name']}  |  {meeting['deal_stage']}")

st.divider()

# --- Build meeting context for the agent's dynamic variables ---
meeting_context = (
    f"Client: {meeting['client_name']} ({meeting['client_contact']}). "
    f"Meeting type: {meeting['type']}. "
    f"Deal: {meeting['deal_name']} - {meeting['deal_stage']} - {meeting['deal_value']}. "
    f"Date: {meeting['date']} at {meeting['time']}. "
    f"Attendees: {', '.join(meeting['attendees'])}. "
    f"Pre-meeting notes: {meeting['notes_pre']}"
)

dynamic_vars = {"meeting_context": meeting_context}

# --- Summary complete ---
if st.session_state.interview_complete and st.session_state.current_summary:
    st.success("Interview complete! Summary generated.")
    if st.button("View Summary", type="primary", use_container_width=True):
        st.switch_page("pages/summary.py")
    st.stop()

# --- Transcript fetch + summary generation ---
if st.session_state.fetching_transcript:
    with st.spinner("Fetching conversation transcript from ElevenLabs..."):
        try:
            # Get the most recent conversation for this agent
            conv_id = get_latest_conversation_id(AGENT_ID)
            if conv_id:
                transcript = fetch_conversation_transcript(conv_id)
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
                        st.rerun()
                elif transcript is None:
                    st.warning("Conversation is still processing. Wait a few seconds and try again.")
                    st.session_state.fetching_transcript = False
                else:
                    st.warning("Transcript was empty. The conversation may not have had any messages.")
                    st.session_state.fetching_transcript = False
            else:
                st.warning("No conversations found for this agent. Make sure you've completed a call first.")
                st.session_state.fetching_transcript = False
        except Exception as e:
            st.error(f"Error: {e}")
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

# --- ElevenLabs Conversational AI Widget ---
st.markdown("### Step 1: Have your debrief conversation")
st.caption("Tap the call button to start. The AI interviewer will ask you about your meeting.")

# Pin the ElevenLabs floating widget to bottom-right, prevent it from jumping around
st.markdown("""
<style>
    elevenlabs-convai {
        position: fixed !important;
        bottom: 20px !important;
        right: 20px !important;
        z-index: 9999 !important;
    }
</style>
""", unsafe_allow_html=True)

_elevenlabs_widget = st.components.v2.component(
    "elevenlabs_widget",
    html="""<div id="elevenlabs-container"></div>""",
    js="""
    export default function({ parentElement, data }) {
        const container = parentElement.querySelector('#elevenlabs-container');
        if (!container) return;
        if (container.dataset.initialized === 'true') return;
        container.dataset.initialized = 'true';

        const widget = document.createElement('elevenlabs-convai');
        widget.setAttribute('agent-id', data.agent_id);
        widget.setAttribute('dynamic-variables', JSON.stringify(data.dynamic_vars));
        container.appendChild(widget);

        const script = document.createElement('script');
        script.src = 'https://unpkg.com/@elevenlabs/convai-widget-embed';
        script.async = true;
        document.head.appendChild(script);
    }
    """,
    isolate_styles=False,
)

_elevenlabs_widget(
    data={"agent_id": AGENT_ID, "dynamic_vars": dynamic_vars},
    key="elevenlabs_voice",
    height=200,
)

# --- End interview ---
st.markdown("---")
st.markdown("### Step 2: End the call, then generate your summary")
st.caption("Hang up in the widget first, then click the button below.")

if st.button("End Interview & Generate Summary", type="primary", use_container_width=True):
    st.session_state.fetching_transcript = True
    st.rerun()
