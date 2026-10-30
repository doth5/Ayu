"""Templates admin page – create, edit, delete message templates."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from app.streamlit.utils import api_client as api

st.set_page_config(page_title="Templates – AyuSynk", page_icon="📝", layout="wide")

SPECIALTIES = [
    "General Physician", "Pediatrician", "Cardiologist", "Pulmonologist",
    "Surgeon", "Anesthesiologist", "Orthopedic", "Emergency Medicine",
    "Gynecologist", "Medical Student", "Professor",
]

st.markdown("""
<div class="page-header">
  <h1>📝 Message Templates</h1>
  <p>Create and manage WhatsApp message templates. Use {doctor_name} and {specialty} as placeholders.</p>
</div>
""", unsafe_allow_html=True)

tab_list, tab_add = st.tabs(["📋 All Templates", "➕ New Template"])

# ── Template list ─────────────────────────────────────────────────────────────
with tab_list:
    search = st.text_input("🔍 Search templates", "")
    filter_spec = st.selectbox("Filter by Specialty", ["All (including universal)"] + SPECIALTIES)

    params = {}
    if search:
        params["search"] = search
    if filter_spec != "All (including universal)":
        params["specialty"] = filter_spec

    try:
        templates = api.get("/api/templates", **params)
    except Exception as e:
        st.error(f"Could not load templates: {e}")
        templates = []

    st.caption(f"{len(templates)} template(s)")

    for tmpl in templates:
        badge = tmpl.get("specialty") or "Universal"
        with st.expander(f"[{tmpl['id']}] {tmpl['name']}  —  *{badge}*", expanded=False):
            col_content, col_meta = st.columns([3, 1])
            with col_content:
                st.text_area(
                    "Content", value=tmpl["content"], height=120,
                    key=f"content_{tmpl['id']}", disabled=True,
                )
                if tmpl.get("placeholders"):
                    ph_str = " ".join([f"`{{{p}}}`" for p in tmpl["placeholders"]])
                    st.markdown(f"**Placeholders detected:** {ph_str}")
            with col_meta:
                st.markdown(f"**Specialty:** {badge}")
                if tmpl.get("tags"):
                    st.markdown(f"**Tags:** {tmpl['tags']}")
                st.markdown(f"**Active:** {'✅' if tmpl['is_active'] else '❌'}")

            # Edit form
            with st.form(f"edit_tmpl_{tmpl['id']}"):
                new_name = st.text_input("Name", value=tmpl["name"])
                new_content = st.text_area("Content", value=tmpl["content"], height=150)
                spec_choices = ["Universal"] + SPECIALTIES
                current_spec = tmpl.get("specialty")
                spec_index = spec_choices.index(current_spec) if current_spec in spec_choices else 0
                new_spec = st.selectbox(
                    "Specialty (leave Universal for all)",
                    spec_choices,
                    index=spec_index,
                )

                new_tags = st.text_input("Tags (comma-separated)", value=tmpl.get("tags") or "")
                new_active = st.checkbox("Active", value=tmpl["is_active"])

                ec1, ec2 = st.columns(2)
                with ec1:
                    save = st.form_submit_button("💾 Save", use_container_width=True)
                with ec2:
                    delete = st.form_submit_button("🗑️ Delete", use_container_width=True)

                # Preview
                st.markdown("---")
                st.markdown("**Live Preview**")
                preview_name = st.text_input("Doctor name for preview", "Dr. Sharma", key=f"prev_{tmpl['id']}")

                if save:
                    try:
                        api.patch(f"/api/templates/{tmpl['id']}", json={
                            "name": new_name,
                            "content": new_content,
                            "specialty": None if new_spec == "Universal" else new_spec,
                            "tags": new_tags or None,
                            "is_active": new_active,
                        })
                        st.success("Template saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

                if delete:
                    try:
                        api.delete(f"/api/templates/{tmpl['id']}")
                        st.success("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Preview rendering
            try:
                preview = api.post(
                    f"/api/templates/{tmpl['id']}/preview",
                    json={"doctor_name": preview_name, "specialty": "Cardiologist"},
                )
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background:#1e2d45;border-left:3px solid #25d366;
                                    border-radius:8px;padding:12px 16px;margin-top:8px;">
                          <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:4px;">WhatsApp Preview</div>
                          <div style="color:#e2e8f0;white-space:pre-wrap;">{preview['rendered']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass

# ── Add Template ─────────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Create New Template")
    with st.form("add_template_form", clear_on_submit=True):
        ac1, ac2 = st.columns([3, 1])
        with ac1:
            t_name = st.text_input("Template Name *", placeholder="e.g. Cardiology Intro")
            t_content = st.text_area(
                "Message Content *",
                height=200,
                placeholder=(
                    "Hello Dr. {doctor_name} 👋\n\n"
                    "I'd like to introduce you to the AyuSynk 2+ digital stethoscope..."
                ),
            )
        with ac2:
            t_specialty = st.selectbox("Specialty", ["Universal"] + SPECIALTIES)
            t_tags = st.text_input("Tags", placeholder="intro, greeting")

        st.markdown(
            "**Available placeholders:** `{doctor_name}` `{specialty}` `{mobile}` `{clinic_name}` `{city}`"
        )
        submitted = st.form_submit_button("➕ Create Template", use_container_width=True)
        if submitted:
            if not t_name or not t_content:
                st.error("Name and content are required.")
            else:
                try:
                    result = api.post("/api/templates", json={
                        "name": t_name,
                        "content": t_content,
                        "specialty": None if t_specialty == "Universal" else t_specialty,
                        "tags": t_tags or None,
                    })
                    st.success(f"✅ Template **{result['name']}** created!")
                except Exception as e:
                    st.error(f"Error: {e}")
