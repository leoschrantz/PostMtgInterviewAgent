"""Post-Meeting Interview Agent - Main entry point."""

import streamlit as st

st.set_page_config(
    page_title="Post-Meeting Debrief Agent",
    page_icon="🎙️",
    layout="centered",
)

# --- Global brand styling ---
st.markdown("""
<style>
    /* Arial font everywhere */
    html, body, [class*="css"], .stMarkdown, .stTextInput, .stTextArea,
    .stSelectbox, .stButton, h1, h2, h3, h4, h5, h6, p, span, div, label {
        font-family: Arial, Helvetica, sans-serif !important;
    }

    /* Primary buttons: black bg, yellow text */
    .stButton > button[kind="primary"] {
        background-color: #000000 !important;
        color: #FFCE00 !important;
        border: 2px solid #FFCE00 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #222222 !important;
        color: #FFCE00 !important;
    }

    /* Secondary buttons: white bg, black text, black border */
    .stButton > button:not([kind="primary"]) {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background-color: #F5F5F5 !important;
    }

    /* Success alerts: green accent */
    .stAlert [data-testid="stAlertContentSuccess"] {
        color: #008B5C !important;
    }

    /* Warning alerts: yellow accent */
    .stAlert [data-testid="stAlertContentWarning"] {
        border-left-color: #FFCE00 !important;
    }

    /* Metrics: black text */
    [data-testid="stMetricValue"] {
        color: #000000 !important;
    }

    /* Links */
    a {
        color: #008B5C !important;
    }

    /* Chat message styling */
    .stChatMessage {
        border-radius: 8px !important;
    }

    /* Container borders */
    [data-testid="stExpander"] {
        border-color: #000000 !important;
    }

    /* Hide the sidebar collapse/expand button on mobile (shows "double_arrow_right" text) */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    button[kind="headerNoPadding"],
    .st-emotion-cache-1egp75f,
    [data-testid="stHeader"] button {
        display: none !important;
    }

    /* Hide sidebar entirely since we use in-page navigation */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    section[data-testid="stSidebar"] {
        display: none !important;
    }

    /* Clean up header area */
    header[data-testid="stHeader"] {
        background-color: #000000 !important;
        height: 0px !important;
        min-height: 0px !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

dashboard = st.Page("pages/dashboard.py", title="Meetings Dashboard", icon="📋", default=True)
interview = st.Page("pages/interview.py", title="Interview", icon="🎙️")
summary = st.Page("pages/summary.py", title="Summary", icon="📝")

pg = st.navigation([dashboard, interview, summary])
pg.run()
