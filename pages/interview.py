"""Interview page - ElevenLabs conversational AI widget for post-meeting debrief."""

import json
import streamlit as st
from mock_data import get_meeting, update_meeting_status
from agent import generate_summary
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
if "captured_transcript" not in st.session_state:
    st.session_state.captured_transcript = None

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

# --- Interview complete: generate summary ---
if st.session_state.interview_complete and st.session_state.captured_transcript:
    if not st.session_state.current_summary:
        with st.spinner("Generating summary from your conversation..."):
            try:
                transcript = st.session_state.captured_transcript
                summary = generate_summary(transcript, meeting)
                st.session_state.current_summary = summary

                update_meeting_status(
                    meeting["id"], "complete",
                    transcript=transcript,
                    summary=summary,
                )
                save_interview(meeting["id"], transcript, summary)
            except Exception as e:
                st.error(f"Error generating summary: {e}")

    if st.session_state.current_summary:
        st.success("Interview complete! Summary generated.")
        if st.button("View Summary", type="primary", use_container_width=True):
            st.switch_page("pages/summary.py")
    st.stop()

# --- ElevenLabs Conversational AI Widget ---
st.markdown("**Tap the call button below to start your debrief conversation:**")
st.caption("The AI interviewer will ask you questions about your meeting. Just talk naturally -- no buttons needed between turns.")

# v2 component: renders in DOM (not iframe), captures transcript via JS events
_noop = lambda: None

_elevenlabs_widget = st.components.v2.component(
    "elevenlabs_widget",
    html="""
    <div id="elevenlabs-container"></div>
    <div id="transcript-status" style="margin-top:8px; font-size:0.85em; color:#888; text-align:center;"></div>
    """,
    js="""
    export default function({ parentElement, data, setTriggerValue, setStateValue }) {
        const container = parentElement.querySelector('#elevenlabs-container');
        const status = parentElement.querySelector('#transcript-status');
        if (!container) return;

        // Only initialize once
        if (container.dataset.initialized === 'true') return;
        container.dataset.initialized = 'true';

        const agentId = data.agent_id;
        const dynamicVars = data.dynamic_vars;

        // Transcript collection
        window.__elevenLabsTranscript = window.__elevenLabsTranscript || [];
        window.__elevenLabsCallActive = false;

        // Create widget
        const widget = document.createElement('elevenlabs-convai');
        widget.setAttribute('agent-id', agentId);
        widget.setAttribute('dynamic-variables', JSON.stringify(dynamicVars));
        container.appendChild(widget);

        // Listen for conversation events
        widget.addEventListener('elevenlabs-convai:call', (event) => {
            window.__elevenLabsTranscript = [];
            window.__elevenLabsCallActive = true;
            status.textContent = 'Conversation active - transcript is being captured...';
            setStateValue('call_active', true);

            // Set up message handler via the event config
            if (event.detail && event.detail.config) {
                event.detail.config.clientTools = event.detail.config.clientTools || {};
            }
        });

        widget.addEventListener('elevenlabs-convai:message', (event) => {
            if (event.detail) {
                const role = event.detail.source === 'ai' ? 'assistant' : 'user';
                const content = event.detail.message || '';
                if (content.trim()) {
                    window.__elevenLabsTranscript.push({ role: role, content: content });
                    const count = window.__elevenLabsTranscript.length;
                    status.textContent = 'Capturing transcript... (' + count + ' messages)';
                }
            }
        });

        widget.addEventListener('elevenlabs-convai:call:ended', (event) => {
            window.__elevenLabsCallActive = false;
            const transcript = window.__elevenLabsTranscript;
            if (transcript && transcript.length > 0) {
                status.textContent = 'Conversation ended. ' + transcript.length + ' messages captured. Click End Interview below.';
                setTriggerValue('transcript', JSON.stringify(transcript));
            } else {
                status.textContent = 'Conversation ended. No messages captured.';
            }
            setStateValue('call_active', false);
        });

        // Also expose a way to manually grab the transcript
        window.__getElevenLabsTranscript = function() {
            return JSON.stringify(window.__elevenLabsTranscript || []);
        };

        // Load the ElevenLabs widget script
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/@elevenlabs/convai-widget-embed';
        script.async = true;
        document.head.appendChild(script);
    }
    """,
    isolate_styles=False,
)

result = _elevenlabs_widget(
    data={"agent_id": AGENT_ID, "dynamic_vars": dynamic_vars},
    key="elevenlabs_voice",
    height=200,
    on_call_active_change=_noop,
    on_transcript_change=_noop,
)

# --- Check if transcript was captured via widget events ---
if result and hasattr(result, "transcript") and result.transcript:
    try:
        transcript_data = json.loads(result.transcript)
        if transcript_data:
            st.session_state.captured_transcript = transcript_data
    except (json.JSONDecodeError, TypeError):
        pass

# --- End Interview button ---
st.markdown("---")

if st.button("End Interview & Generate Summary", type="primary", use_container_width=True):
    if st.session_state.captured_transcript:
        st.session_state.interview_complete = True
        st.rerun()
    else:
        st.warning("No conversation captured yet. Have your conversation first, then end the call in the widget before clicking this button.")
