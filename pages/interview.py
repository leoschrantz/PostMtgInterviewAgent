"""Interview page - ElevenLabs conversational AI widget for post-meeting debrief."""

import streamlit as st
import streamlit.components.v1 as components
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

# --- Build meeting context for the agent's system prompt ---
meeting_context = (
    f"Client: {meeting['client_name']} ({meeting['client_contact']})\n"
    f"Meeting type: {meeting['type']}\n"
    f"Deal: {meeting['deal_name']} - {meeting['deal_stage']} - {meeting['deal_value']}\n"
    f"Date: {meeting['date']} at {meeting['time']}\n"
    f"Attendees: {', '.join(meeting['attendees'])}\n"
    f"Pre-meeting notes: {meeting['notes_pre']}"
)

# Escape for safe JS embedding
meeting_context_js = meeting_context.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$").replace("\n", "\\n")

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
                    st.warning("Could not retrieve transcript. The conversation may still be processing.")
            except Exception as e:
                st.error(f"Error fetching transcript: {e}")

    if st.session_state.current_summary:
        st.success("Interview complete! Summary generated.")
        if st.button("View Summary", type="primary", use_container_width=True):
            st.switch_page("pages/summary.py")
        st.stop()

# --- ElevenLabs Conversational AI Widget ---
st.markdown("**Tap the mic below to start your debrief conversation:**")
st.caption("The AI interviewer will ask you questions about your meeting. Just talk naturally.")

widget_html = f"""
<script src="https://cdn.jsdelivr.net/npm/@elevenlabs/convai-widget@latest/dist/index.js" async></script>
<div id="widget-container" style="display:flex; flex-direction:column; align-items:center; padding:20px 0;">
    <elevenlabs-convai
        agent-id="{AGENT_ID}"
        dynamic-variables='{{"meeting_context": "{meeting_context_js}"}}'
    ></elevenlabs-convai>
    <div id="conv-status" style="margin-top:16px; font-size:0.9em; color:#666;"></div>
    <button id="end-btn" onclick="endConversation()" style="
        display:none; margin-top:12px; padding:12px 24px;
        background:#0066cc; color:white; border:none; border-radius:8px;
        font-size:1em; cursor:pointer; width:100%;
    ">End Interview & Generate Summary</button>
</div>
<script>
    // Listen for the widget to be ready and capture conversation ID
    let convId = null;
    const widget = document.querySelector('elevenlabs-convai');

    if (widget) {{
        widget.addEventListener('elevenlabs-convai:call', (event) => {{
            if (event.detail && event.detail.conversationId) {{
                convId = event.detail.conversationId;
                document.getElementById('conv-status').textContent = 'Conversation active...';
                document.getElementById('end-btn').style.display = 'block';
            }}
        }});

        widget.addEventListener('elevenlabs-convai:call:ended', (event) => {{
            if (event.detail && event.detail.conversationId) {{
                convId = event.detail.conversationId;
            }}
            document.getElementById('conv-status').textContent = 'Conversation ended.';
        }});
    }}

    function endConversation() {{
        // Post the conversation ID back to Streamlit via query params
        if (convId) {{
            // Use URL to pass data back to Streamlit
            const url = new URL(window.parent.location.href);
            url.searchParams.set('conv_id', convId);
            url.searchParams.set('done', 'true');
            window.parent.location.href = url.toString();
        }} else {{
            document.getElementById('conv-status').textContent = 'No conversation to end. Start talking first!';
        }}
    }}
</script>
"""

components.html(widget_html, height=400)

# --- Check if returning from conversation end ---
query_params = st.query_params
conv_id = query_params.get("conv_id")
done = query_params.get("done")

if done == "true" and conv_id:
    st.session_state.conversation_id = conv_id
    st.session_state.interview_complete = True
    # Clear query params
    st.query_params.clear()
    st.rerun()

# --- Text fallback note ---
st.markdown("---")
st.caption("If voice isn't working, you can use the text input in the ElevenLabs widget.")
