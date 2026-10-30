"""
AyuSynk Sales Pipeline – Main Streamlit entry point.
Run with: streamlit run app/streamlit/main.py
"""
import sys
from pathlib import Path

# Ensure project root is on the Python path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="AyuSynk Sales Pipeline",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark gradient background */
.stApp {
    background: linear-gradient(135deg, #0d0f1a 0%, #111827 50%, #0a0e1a 100%);
    color: #e2e8f0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111827 0%, #0d1424 100%);
    border-right: 1px solid #1e2d45;
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #60a5fa;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1e2d45 0%, #1a2538 100%);
    border: 1px solid #2d4a6e;
    border-radius: 12px;
    padding: 16px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(96,165,250,0.15);
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #60a5fa;
    font-weight: 700;
    font-size: 2rem;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 8px 20px;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(59,130,246,0.4);
}

/* Form inputs */
.stTextInput input, .stSelectbox select, .stTextArea textarea {
    background: #1e2d45 !important;
    border: 1px solid #2d4a6e !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}

/* Success / Error */
.stSuccess {
    background: rgba(16, 185, 129, 0.1) !important;
    border: 1px solid #10b981 !important;
    border-radius: 8px !important;
}
.stError {
    background: rgba(239, 68, 68, 0.1) !important;
    border: 1px solid #ef4444 !important;
    border-radius: 8px !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: #1e2d45 !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}

/* Tables */
.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
}

/* Tab */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    background: #1e2d45;
    border-radius: 8px 8px 0 0;
    color: #94a3b8;
    border: none;
    padding: 8px 20px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: white !important;
}

/* Badge-like chips */
.specialty-badge {
    display: inline-block;
    background: linear-gradient(135deg, #1e3a5f 0%, #1e2d45 100%);
    border: 1px solid #2d4a6e;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.75rem;
    color: #60a5fa;
    font-weight: 500;
}

/* Header gradient */
.page-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #1e2d45 100%);
    border: 1px solid #2d4a6e;
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
}
.page-header h1 { color: #60a5fa; margin: 0; font-size: 1.8rem; font-weight: 800; }
.page-header p  { color: #94a3b8; margin: 4px 0 0; font-size: 0.95rem; }

/* WhatsApp button */
.wa-btn {
    display: inline-block;
    background: linear-gradient(135deg, #25d366 0%, #128c7e 100%);
    color: white !important;
    text-decoration: none !important;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 0.9rem;
    transition: all 0.2s ease;
}
.wa-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(37,211,102,0.4);
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Sidebar logo / nav ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center;padding:20px 0 24px;">
          <div style="font-size:2.5rem;">🩺</div>
          <div style="font-size:1.2rem;font-weight:800;color:#60a5fa;letter-spacing:0.5px;">AyuSynk</div>
          <div style="font-size:0.7rem;color:#64748b;letter-spacing:2px;text-transform:uppercase;margin-top:2px;">Sales Pipeline</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

# ── Home page ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="page-header">
      <h1>🩺 AyuSynk 2+ Sales Pipeline</h1>
      <p>Automated WhatsApp outreach management for AyuSynk digital stethoscope.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**📊 Dashboard** — View stats and pipeline health", icon="📊")
with col2:
    st.info("**👨‍⚕️ Doctors** — Add and manage contacts", icon="👨‍⚕️")
with col3:
    st.info("**📤 Send Messages** — Daily message queue", icon="📤")

col4, col5, col6 = st.columns(3)
with col4:
    st.info("**🔧 Pipelines** — Configure step sequences", icon="🔧")
with col5:
    st.info("**📝 Templates** — Manage message templates", icon="📝")
with col6:
    st.info("**📁 Media** — Upload videos, PDFs, images", icon="📁")

st.markdown(
    """
    <div style="text-align:center;margin-top:32px;color:#475569;font-size:0.85rem;">
      Use the sidebar to navigate between pages.
    </div>
    """,
    unsafe_allow_html=True,
)
