"""Dashboard page."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from app.streamlit.utils import api_client as api

st.set_page_config(page_title="Dashboard – AyuSynk", page_icon="📊", layout="wide")

st.markdown("""
<div class="page-header">
  <h1>📊 Dashboard</h1>
  <p>Live overview of your sales pipeline activity.</p>
</div>
""", unsafe_allow_html=True)

try:
    stats = api.get("/api/dashboard/stats")
except Exception as e:
    st.error(f"Could not connect to API: {e}")
    st.stop()

# ── KPI Row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("👨‍⚕️ Total Doctors",     stats["total_doctors"])
c2.metric("✅ Active Pipelines",   stats["active_pipelines"])
c3.metric("⏰ Due Today",          stats["due_today"])
c4.metric("📤 Pending Messages",   stats["pending_messages"])
c5.metric("📨 Sent Today",         stats["sent_today"])
c6.metric("❌ Failed",             stats["failed_executions"])

st.divider()

# ── Row 2 ─────────────────────────────────────────────────────────────────────
col_a, col_b = st.columns([1, 2])

with col_a:
    st.subheader("Pipeline Status")
    status_data = {
        "Status": ["Active", "Paused", "Completed"],
        "Count": [
            stats["active_pipelines"],
            stats["paused_pipelines"],
            stats["completed_pipelines"],
        ],
    }
    st.dataframe(pd.DataFrame(status_data), use_container_width=True, hide_index=True)

    st.metric("🚫 Opted Out", stats["opted_out_doctors"])

with col_b:
    st.subheader("Doctors by Specialty")
    if stats["by_specialty"]:
        spec_df = pd.DataFrame(
            [{"Specialty": k, "Count": v} for k, v in stats["by_specialty"].items()]
        ).sort_values("Count", ascending=False)
        st.bar_chart(spec_df.set_index("Specialty"))
    else:
        st.info("No doctors added yet.")

st.divider()

# ── Recent Activity ───────────────────────────────────────────────────────────
st.subheader("📋 Recent Message Activity")
try:
    logs = api.get("/api/dashboard/recent-logs")
    if logs:
        df = pd.DataFrame(logs)
        df["sent_at"] = pd.to_datetime(df["sent_at"]).dt.strftime("%Y-%m-%d %H:%M")
        df = df[["doctor_name", "mobile", "direction", "status", "message_preview", "sent_at"]]
        df.columns = ["Doctor", "Mobile", "Direction", "Status", "Message Preview", "Sent At"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        # CSV export
        csv = df.to_csv(index=False)
        st.download_button("⬇️ Export CSV", csv, "recent_activity.csv", "text/csv")
    else:
        st.info("No messages sent yet.")
except Exception as e:
    st.warning(f"Could not load logs: {e}")

if st.button("🔄 Refresh Dashboard"):
    st.rerun()
