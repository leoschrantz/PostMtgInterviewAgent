"""Interview page - ElevenLabs conversational AI widget for post-meeting debrief."""

import json
import streamlit as st
from pathlib import Path
from mock_data import get_meeting, update_meeting_status
from agent import generate_summary, fetch_conversation_transcript
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
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False

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

# Build the dynamic variables dict for the widget
dynamic_vars = {"meeting_context": meeting_context}

# --- Interview complete: show summary flow ---
if st.session_state.interview_complete and st.session_state.conversation_id:
    if not st.session_state.current_summary:
        with st.spinner("Fetching transcript and generating summary..."):
            try:
                transcript = fetch_conversation_transcript(
                    st.session_state.conversation_id
                )
                if transcript:
                    summary = generate_summary(transcript, meeting)
                    st.session_state.current_summary = summary

                    update_meeting_status(
                        meeting["id"], "complete",
                        transcript=transcript,
                        summary=summary,
                    )
                    save_interview(meeting["id"], transcript, summary)
                else:
                    st.warning("Could not retrieve transcript yet. The conversation may still be processing. Try again in a moment.")
                    if st.button("Retry", use_container_width=True):
                        st.rerun()
            except Exception as e:
                st.error(f"Error fetching transcript: {e}")
                if st.button("Retry", use_container_width=True):
                    st.rerun()

    if st.session_state.current_summary:
        st.success("Interview complete! Summary generated.")
        if st.button("View Summary", type="primary", use_container_width=True):
            st.switch_page("pages/summary.py")
    st.stop()

# --- ElevenLabs Conversational AI Widget ---
st.markdown("**Tap the call button below to start your debrief conversation:**")
st.caption("The AI interviewer will ask you questions about your meeting. Just talk naturally -- no buttons needed between turns.")

# Use a v2 component with isolate_styles=False to render directly in the DOM
# (no iframe = mic/speaker permissions work, script tags execute)
# Pass dynamic vars via data parameter (properly JSON-serialized by Streamlit)
_elevenlabs_widget = st.components.v2.component(
    "elevenlabs_widget",
    html="""
    <div id="elevenlabs-container"></div>
    """,
    js="""
    export default function({ parentElement, data }) {
        const container = parentElement.querySelector('#elevenlabs-container');
        if (!container) return;
        // Only initialize once
        if (container.dataset.initialized === 'true') return;
        container.dataset.initialized = 'true';

        const agentId = data.agent_id;
        const dynamicVars = data.dynamic_vars;

        // Create and insert the widget element
        const widget = document.createElement('elevenlabs-convai');
        widget.setAttribute('agent-id', agentId);
        widget.setAttribute('dynamic-variables', JSON.stringify(dynamicVars));
        container.appendChild(widget);

        // Load the ElevenLabs widget script
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

# --- Manual conversation ID input + end button ---
st.markdown("---")
st.markdown("When you're done with the conversation, paste the conversation ID below and click End Interview.")
st.caption("You can find the conversation ID in the ElevenLabs dashboard under Conversations, or just click End Interview to enter it.")

conv_id_input = st.text_input(
    "Conversation ID (from ElevenLabs)",
    value=st.session_state.get("conversation_id", ""),
    placeholder="e.g. abc123def456...",
)

if st.button("End Interview & Generate Summary", type="primary", use_container_width=True):
    if conv_id_input:
        st.session_state.conversation_id = conv_id_input
        st.session_state.interview_complete = True
        st.rerun()
    else:
        st.warning("Please enter the conversation ID from ElevenLabs to generate the summary.")
