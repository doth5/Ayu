"""Pipelines admin page – configure specialty pipelines and their steps."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from app.streamlit.utils import api_client as api

st.set_page_config(page_title="Pipelines – AyuSynk", page_icon="🔧", layout="wide")

st.markdown("""
<div class="page-header">
  <h1>🔧 Pipeline Configuration</h1>
  <p>Manage specialty-specific sales pipelines and their step sequences.</p>
</div>
""", unsafe_allow_html=True)

try:
    pipelines = api.get("/api/pipelines")
except Exception as e:
    st.error(f"Could not connect to API: {e}")
    st.stop()

if not pipelines:
    st.warning("No pipelines found. They are created automatically when the app first starts.")
    st.stop()

# ── Pipeline selector ─────────────────────────────────────────────────────────
pipeline_map = {f"{p['specialty']} ({p['name']})": p for p in pipelines}
selected_key = st.selectbox(
    "Select Pipeline to Configure",
    list(pipeline_map.keys()),
)
pipeline = pipeline_map[selected_key]

col_info, col_toggle = st.columns([4, 1])
with col_info:
    st.markdown(f"**Pipeline:** {pipeline['name']}  |  **Specialty:** {pipeline['specialty']}")
    desc = st.text_input("Description", value=pipeline.get("description") or "", key="desc")
    if st.button("💾 Save Description"):
        api.patch(f"/api/pipelines/{pipeline['id']}", json={"description": desc})
        st.success("Saved.")
with col_toggle:
    is_active = pipeline["is_active"]
    new_state = st.toggle("Pipeline Active", value=is_active, key="active_toggle")
    if new_state != is_active:
        api.patch(f"/api/pipelines/{pipeline['id']}", json={"is_active": new_state})
        st.rerun()

st.divider()

# ── Step list ─────────────────────────────────────────────────────────────────
st.subheader(f"📋 Steps ({len(pipeline['steps'])} configured)")

if pipeline["steps"]:
    for step in sorted(pipeline["steps"], key=lambda s: s["step_order"]):
        with st.expander(f"Step {step['step_order']}: {step['name']}", expanded=False):
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f"**Type:** {step['step_type']}")
                st.markdown(f"**Delay before this step:** {step['delay_hours']} hours")
                st.markdown(f"**Active:** {'✅' if step['is_active'] else '❌'}")
            with sc2:
                st.markdown(f"**Template ID:** {step.get('template_id', 'None')}")
                st.markdown(f"**Media ID:** {step.get('media_file_id', 'None')}")
                if step.get("conditions"):
                    st.markdown(f"**Conditions:** `{step['conditions']}`")

            # Quick edit
            with st.form(f"edit_step_{step['id']}"):
                new_name = st.text_input("Step Name", value=step["name"])
                new_delay = st.number_input(
                    "Delay (hours before this step)", value=float(step["delay_hours"]),
                    min_value=0.0, step=1.0,
                )
                new_active = st.checkbox("Active", value=step["is_active"])

                # Template picker
                try:
                    templates = api.get("/api/templates")
                    tmpl_options = {f"[{t['id']}] {t['name']}": t["id"] for t in templates}
                except Exception:
                    tmpl_options = {}

                current_tmpl = (
                    next((k for k, v in tmpl_options.items() if v == step.get("template_id")), None)
                    if tmpl_options else None
                )
                tmpl_choices = ["(none)"] + list(tmpl_options.keys())
                sel_tmpl = st.selectbox(
                    "Template", tmpl_choices,
                    index=tmpl_choices.index(current_tmpl) if current_tmpl in tmpl_choices else 0,
                )

                # Media picker
                try:
                    media_list = api.get("/api/media")
                    media_options = {f"[{m['id']}] {m['name']}": m["id"] for m in media_list}
                except Exception:
                    media_options = {}

                current_media = (
                    next((k for k, v in media_options.items() if v == step.get("media_file_id")), None)
                    if media_options else None
                )
                media_choices = ["(none)"] + list(media_options.keys())
                sel_media = st.selectbox(
                    "Media File", media_choices,
                    index=media_choices.index(current_media) if current_media in media_choices else 0,
                )

                conditions = st.text_input(
                    "Conditions (JSON)", value=step.get("conditions") or "",
                    help='e.g. {"require_no_reply": true}',
                )

                scol1, scol2 = st.columns(2)
                with scol1:
                    save_step = st.form_submit_button("💾 Save Step", use_container_width=True)
                with scol2:
                    del_step = st.form_submit_button("🗑️ Delete Step", use_container_width=True)

                if save_step:
                    update = {
                        "name": new_name,
                        "delay_hours": new_delay,
                        "is_active": new_active,
                        "template_id": tmpl_options.get(sel_tmpl),
                        "media_file_id": media_options.get(sel_media),
                        "conditions": conditions or None,
                    }
                    api.patch(f"/api/pipelines/{pipeline['id']}/steps/{step['id']}", json=update)
                    st.success("Step updated!")
                    st.rerun()

                if del_step:
                    api.delete(f"/api/pipelines/{pipeline['id']}/steps/{step['id']}")
                    st.success("Step deleted.")
                    st.rerun()

else:
    st.info("No steps configured for this pipeline. Add one below.")

st.divider()

# ── Add new step ──────────────────────────────────────────────────────────────
st.subheader("➕ Add New Step")
with st.form("add_step_form", clear_on_submit=True):
    ac1, ac2 = st.columns(2)
    with ac1:
        new_step_name = st.text_input("Step Name *", placeholder="e.g. Send Demo Video")
        new_step_order = st.number_input(
            "Step Order *", min_value=1,
            value=max((s["step_order"] for s in pipeline["steps"]), default=0) + 1,
        )
        new_step_type = st.selectbox("Step Type", ["text", "image", "video", "document", "mixed"])
        new_delay = st.number_input("Delay Hours", min_value=0.0, value=24.0, step=1.0)
    with ac2:
        try:
            templates_list = api.get("/api/templates")
            tmpl_add_map = {f"[{t['id']}] {t['name']}": t["id"] for t in templates_list}
        except Exception:
            tmpl_add_map = {}

        tmpl_add_choices = ["(none)"] + list(tmpl_add_map.keys())
        sel_tmpl_add = st.selectbox("Template", tmpl_add_choices)

        try:
            media_add_list = api.get("/api/media")
            media_add_map = {f"[{m['id']}] {m['name']}": m["id"] for m in media_add_list}
        except Exception:
            media_add_map = {}

        media_add_choices = ["(none)"] + list(media_add_map.keys())
        sel_media_add = st.selectbox("Media File", media_add_choices)

        new_conditions = st.text_input("Conditions (JSON)", placeholder='{"require_no_reply": true}')

    add_submitted = st.form_submit_button("➕ Add Step", use_container_width=True)
    if add_submitted:
        if not new_step_name:
            st.error("Step name is required.")
        else:
            try:
                api.post(f"/api/pipelines/{pipeline['id']}/steps", json={
                    "step_order": int(new_step_order),
                    "name": new_step_name,
                    "step_type": new_step_type,
                    "delay_hours": float(new_delay),
                    "template_id": tmpl_add_map.get(sel_tmpl_add),
                    "media_file_id": media_add_map.get(sel_media_add),
                    "conditions": new_conditions or None,
                })
                st.success(f"Step '{new_step_name}' added!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
