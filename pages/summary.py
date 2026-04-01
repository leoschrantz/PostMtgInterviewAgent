"""Summary page - displays structured interview summary and raw transcript."""

import json
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


# --- Helper: convert structured summary to markdown ---
def summary_to_markdown(s: dict) -> str:
    """Convert summary dict to a clean markdown string."""
    lines = []

    lines.append(f"## Meeting Outcome\n{s.get('meeting_outcome', 'N/A')}")

    takeaways = s.get("key_takeaways", [])
    if takeaways:
        lines.append("## Key Takeaways")
        for t in takeaways:
            lines.append(f"- {t}")

    lines.append(f"\n## Client Sentiment\n{s.get('client_sentiment', 'N/A')}")

    action_items = s.get("action_items", [])
    if action_items:
        lines.append("## Action Items")
        for item in action_items:
            owner = item.get("owner", "TBD")
            action = item.get("action", "")
            deadline = item.get("deadline", "TBD")
            lines.append(f"- **{owner}:** {action} *(by {deadline})*")

    deal_status = s.get("deal_status", {})
    if deal_status:
        lines.append("## Deal Status Assessment")
        lines.append(f"- **Recommended Stage:** {deal_status.get('stage_recommendation', 'N/A')}")
        lines.append(f"- **Confidence:** {deal_status.get('confidence_level', 'N/A')}")
        lines.append(f"- **Deal Value:** {deal_status.get('deal_value_change', 'no change')}")
        risks = deal_status.get("risks", [])
        if risks:
            lines.append("- **Risks:**")
            for risk in risks:
                lines.append(f"  - {risk}")

    follow_up = s.get("follow_up_date")
    if follow_up:
        lines.append(f"\n## Suggested Follow-up\n{follow_up}")

    additional = s.get("additional_notes")
    if additional:
        lines.append(f"\n## Additional Notes\n{additional}")

    return "\n".join(lines)


# --- Initialize edit state ---
if "editing_summary" not in st.session_state:
    st.session_state.editing_summary = False
if "summary_markdown" not in st.session_state or not st.session_state.get("summary_markdown"):
    st.session_state.summary_markdown = summary_to_markdown(summary)


# --- Edit / View toggle ---
edit_col, spacer = st.columns([1, 3])
with edit_col:
    if st.session_state.editing_summary:
        if st.button("Save", type="primary", use_container_width=True):
            st.session_state.editing_summary = False
            st.rerun()
    else:
        if st.button("Edit Summary", use_container_width=True):
            st.session_state.editing_summary = True
            st.rerun()


# --- Display summary ---
if st.session_state.editing_summary:
    st.session_state.summary_markdown = st.text_area(
        "Edit your summary (Markdown supported)",
        value=st.session_state.summary_markdown,
        height=500,
        key="summary_editor",
    )
else:
    st.markdown(st.session_state.summary_markdown)

st.divider()

# --- Download buttons ---
st.markdown("### Export")
dl_cols = st.columns(2)

with dl_cols[0]:
    st.download_button(
        "Download Summary (.md)",
        data=st.session_state.summary_markdown,
        file_name=f"{meeting['client_name'].replace(' ', '_')}_debrief_summary.md",
        mime="text/markdown",
        type="primary",
        use_container_width=True,
    )

with dl_cols[1]:
    transcript_text = format_transcript(transcript) if transcript else "No transcript available."
    st.download_button(
        "Download Transcript (.md)",
        data=transcript_text,
        file_name=f"{meeting['client_name'].replace(' ', '_')}_transcript.md",
        mime="text/markdown",
        use_container_width=True,
    )

# --- Raw Transcript ---
st.divider()
with st.expander("View Raw Interview Transcript"):
    if transcript:
        st.markdown(format_transcript(transcript))
    else:
        st.markdown("*No transcript available.*")
