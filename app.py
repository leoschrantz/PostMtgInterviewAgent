"""Post-Meeting Interview Agent - Main entry point."""

import streamlit as st

st.set_page_config(
    page_title="Post-Meeting Debrief Agent",
    page_icon="🎙️",
    layout="centered",
)

dashboard = st.Page("pages/dashboard.py", title="Meetings Dashboard", icon="📋", default=True)
interview = st.Page("pages/interview.py", title="Interview", icon="🎙️")
summary = st.Page("pages/summary.py", title="Summary", icon="📝")

pg = st.navigation([dashboard, interview, summary])
pg.run()
