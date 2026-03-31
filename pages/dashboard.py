"""Meetings Dashboard - displays mock Dynamics CRM meetings with interview status."""

import streamlit as st
from mock_data import get_all_meetings

st.title("Meetings Dashboard")
st.caption("Microsoft Dynamics CRM  |  Post-Meeting Interview Tracker")

st.divider()

meetings = get_all_meetings()

# Summary metrics
col1, col2, col3 = st.columns(3)
total = len(meetings)
complete = sum(1 for m in meetings if m["status"] == "complete")
pending = total - complete

col1.metric("Total Meetings", total)
col2.metric("Interviews Complete", complete)
col3.metric("Interviews Pending", pending)

st.divider()

# Meeting cards - stacked layout for mobile friendliness
for meeting in meetings:
    with st.container(border=True):
        st.subheader(f"{meeting['client_name']}")
        st.caption(f"{meeting['type']}  |  {meeting['date']} at {meeting['time']}")

        st.markdown(f"**Contact:** {meeting['client_contact']}")
        st.markdown(f"**Deal:** {meeting['deal_name']}  |  {meeting['deal_value']}  |  {meeting['deal_stage']}")

        if meeting["status"] == "complete":
            st.success("Interview Complete")
            if st.button("View Summary", key=f"view_{meeting['id']}", use_container_width=True):
                st.session_state.active_meeting_id = meeting["id"]
                st.switch_page("pages/summary.py")
        else:
            st.warning("Interview Pending")
            if st.button(
                "Start Interview",
                key=f"start_{meeting['id']}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.active_meeting_id = meeting["id"]
                # Reset interview state for a fresh start
                st.session_state.conversation_history = []
                st.session_state.interview_started = False
                st.session_state.interview_complete = False
                st.session_state.current_tts_text = ""
                st.session_state.tts_counter = 0
                st.session_state.current_summary = None
                st.switch_page("pages/interview.py")
