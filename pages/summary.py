"""Summary page - displays structured interview summary and raw transcript."""

import streamlit as st
from mock_data import get_meeting
from utils import format_transcript

# --- Guard: must have an active meeting ---
if "active_meeting_id" not in st.session_state or not st.session_state.active_meeting_id:
    st.warning("No meeting selected.")
    if st.button("Go to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

meeting = get_meeting(st.session_state.active_meeting_id)
if not meeting:
    st.error("Meeting not found.")
    st.stop()

# Get summary from meeting data or session state
summary = st.session_state.get("current_summary") or meeting.get("summary")
transcript = meeting.get("transcript") or st.session_state.get("conversation_history", [])

if not summary:
    st.warning("No summary available for this meeting yet.")
    if st.button("Go to Dashboard"):
        st.switch_page("pages/dashboard.py")
    st.stop()

# --- Header (stacked for mobile) ---
if st.button("< Dashboard"):
    st.switch_page("pages/dashboard.py")
st.subheader(f"{meeting['client_name']} - Debrief Summary")
st.caption(f"{meeting['date']}  |  {meeting['type']}  |  {meeting['deal_name']}")

st.divider()

# --- Handle error case ---
if "error" in summary:
    st.error("Summary generation encountered an issue.")
    st.code(summary.get("raw", "No details available"))
    st.stop()

# --- Meeting Outcome ---
st.markdown("### Meeting Outcome")
st.info(summary.get("meeting_outcome", "N/A"))

# --- Key Takeaways ---
st.markdown("### Key Takeaways")
for takeaway in summary.get("key_takeaways", []):
    st.markdown(f"- {takeaway}")

# --- Client Sentiment ---
st.markdown("### Client Sentiment")
sentiment = summary.get("client_sentiment", "N/A")
if "positive" in sentiment.lower():
    st.success(sentiment)
elif "negative" in sentiment.lower():
    st.error(sentiment)
else:
    st.warning(sentiment)

# --- Action Items ---
st.markdown("### Action Items")
action_items = summary.get("action_items", [])
if action_items:
    for item in action_items:
        owner = item.get("owner", "TBD")
        action = item.get("action", "")
        deadline = item.get("deadline", "TBD")
        st.markdown(f"- **{owner}:** {action} *(by {deadline})*")
else:
    st.markdown("*No action items identified.*")

# --- Deal Status ---
st.markdown("### Deal Status Assessment")
deal_status = summary.get("deal_status", {})
if deal_status:
    ds_cols = st.columns(2)
    ds_cols[0].metric("Recommended Stage", deal_status.get("stage_recommendation", "N/A"))
    ds_cols[1].metric("Confidence", deal_status.get("confidence_level", "N/A"))

    value_change = deal_status.get("deal_value_change", "no change")
    st.markdown(f"**Deal Value:** {value_change}")

    risks = deal_status.get("risks", [])
    if risks:
        st.markdown("**Risks:**")
        for risk in risks:
            st.markdown(f"- {risk}")

# --- Follow-up ---
follow_up = summary.get("follow_up_date")
if follow_up:
    st.markdown(f"### Suggested Follow-up: {follow_up}")

# --- Additional Notes ---
additional = summary.get("additional_notes")
if additional:
    st.markdown("### Additional Notes")
    st.markdown(additional)

st.divider()

# --- Mock Dynamics Sync ---
st.markdown("### Sync to Microsoft Dynamics")
if st.button("Sync Summary to Dynamics CRM", type="primary", use_container_width=True):
    st.toast("Summary synced to Microsoft Dynamics CRM!", icon="✅")
    st.balloons()
if st.button("Sync Raw Transcript to Dynamics CRM", use_container_width=True):
    st.toast("Raw transcript synced to Microsoft Dynamics CRM!", icon="✅")

# --- Raw Transcript ---
st.divider()
with st.expander("View Raw Interview Transcript"):
    if transcript:
        st.markdown(format_transcript(transcript))
    else:
        st.markdown("*No transcript available.*")
