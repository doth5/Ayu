"""Doctors management page."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from app.streamlit.utils import api_client as api

st.set_page_config(page_title="Doctors – AyuSynk", page_icon="👨‍⚕️", layout="wide")

SPECIALTIES = [
    "General Physician", "Pediatrician", "Cardiologist", "Pulmonologist",
    "Surgeon", "Anesthesiologist", "Orthopedic", "Emergency Medicine",
    "Gynecologist", "Medical Student", "Professor",
]


# ── Dialogs ───────────────────────────────────────────────────────────────────

@st.dialog("✏️ Edit Doctor Details")
def show_edit_dialog(doctor: dict):
    """Modal dialog to update doctor information with real-time validation."""
    st.markdown(f"Updating records for **Dr. {doctor['name']}** `(ID: {doctor['id']})`")

    with st.form(f"edit_doctor_form_{doctor['id']}"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *", value=doctor.get("name") or "")
            mobile = st.text_input(
                "WhatsApp Number (with country code) *",
                value=doctor.get("mobile") or "",
                help="Must include country code, e.g. +919876543210",
            )
            spec_idx = (
                SPECIALTIES.index(doctor["specialty"])
                if doctor.get("specialty") in SPECIALTIES
                else 0
            )
            specialty = st.selectbox("Specialty *", SPECIALTIES, index=spec_idx)

            status_options = ["active", "paused", "completed", "stopped"]
            curr_status = doctor.get("status", "active")
            status_idx = status_options.index(curr_status) if curr_status in status_options else 0
            status = st.selectbox("Status", status_options, index=status_idx)

        with col2:
            clinic = st.text_input("Clinic / Hospital Name", value=doctor.get("clinic_name") or "")
            city = st.text_input("City", value=doctor.get("city") or "")
            opted_out = st.checkbox(
                "🚫 Opted Out of Outreach",
                value=bool(doctor.get("opted_out", False)),
                help="If checked, this doctor is excluded from all automated WhatsApp messages and drip sequences.",
            )
            notes = st.text_area("Notes", value=doctor.get("notes") or "", height=80)

        c_submit, c_cancel = st.columns([1, 1])
        with c_submit:
            saved = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
        with c_cancel:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if cancelled:
            st.rerun()

        if saved:
            clean_name = name.strip()
            clean_mobile = mobile.strip().replace(" ", "").replace("-", "")

            # Validation checks
            if not clean_name:
                st.error("Doctor name is required.")
                return
            if not clean_mobile.startswith("+") or not clean_mobile[1:].isdigit():
                st.error("Mobile number must start with '+' followed by country code and digits (e.g. +919876543210).")
                return
            if len(clean_mobile[1:]) < 10:
                st.error("Mobile number must have at least 10 digits after the country code.")
                return

            try:
                updated = api.patch(
                    f"/api/doctors/{doctor['id']}",
                    json={
                        "name": clean_name,
                        "mobile": clean_mobile,
                        "specialty": specialty,
                        "clinic_name": clinic.strip() or None,
                        "city": city.strip() or None,
                        "notes": notes.strip() or None,
                        "status": status,
                        "opted_out": opted_out,
                    },
                )
                st.success(f"✅ Successfully updated Dr. {updated['name']}!")
                st.rerun()
            except Exception as e:
                err_text = str(e)
                if "already exists" in err_text or "already has mobile" in err_text:
                    st.error(f"❌ Duplicate Error: Mobile number `{clean_mobile}` is already registered to another doctor.")
                else:
                    st.error(f"❌ Update failed: {e}")


@st.dialog("⚠️ Confirm Permanent Deletion")
def show_delete_dialog(doctor: dict):
    """Modal confirmation dialog for destructive doctor deletion."""
    st.error(f"Are you sure you want to permanently delete **Dr. {doctor['name']}**?")
    st.markdown(
        f"""
        - **Doctor ID:** `{doctor['id']}`
        - **WhatsApp Mobile:** `{doctor['mobile']}`
        - **Specialty:** `{doctor['specialty']}`
        - **City:** `{doctor.get('city') or 'N/A'}`

        > ⚠️ **Warning:** This will permanently delete this doctor's contact record,
        > active campaign enrollments, pending executions, and message logs.
        > **This action cannot be undone.**
        """
    )

    c_del, c_abort = st.columns(2)
    with c_del:
        if st.button("🔴 Yes, Permanently Delete", type="primary", use_container_width=True):
            try:
                api.delete(f"/api/doctors/{doctor['id']}")
                st.success(f"Dr. {doctor['name']} was permanently deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to delete doctor: {e}")
    with c_abort:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


# ── Page Header ───────────────────────────────────────────────────────────────

st.markdown("""
<div class="page-header">
  <h1>👨‍⚕️ Doctor Management</h1>
  <p>Search, update, organize, and control outreach eligibility for all doctor contacts across India.</p>
</div>
""", unsafe_allow_html=True)


# ── Load Doctors Data ─────────────────────────────────────────────────────────

try:
    all_doctors = api.get("/api/doctors")
except Exception as e:
    st.error(f"Could not connect to backend API: {e}")
    all_doctors = []

active_doctors = [d for d in all_doctors if not d.get("opted_out", False)]
opted_out_doctors = [d for d in all_doctors if d.get("opted_out", False)]


# ── Overview Metric Cards ─────────────────────────────────────────────────────

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Total Active Doctors", len(active_doctors))
with m2:
    st.metric("Opted-Out Doctors", len(opted_out_doctors))
with m3:
    specs_count = len({d["specialty"] for d in all_doctors if d.get("specialty")})
    st.metric("Specialties Represented", specs_count)
with m4:
    active_in_pipeline = len([d for d in active_doctors if d.get("status") == "active"])
    st.metric("Active in Outreach", active_in_pipeline)

st.markdown("<br>", unsafe_allow_html=True)


# ── Main Tabs ─────────────────────────────────────────────────────────────────

tab_active, tab_opted_out, tab_add = st.tabs([
    f"📋 Active Doctors ({len(active_doctors)})",
    f"🚫 Opted-Out Doctors ({len(opted_out_doctors)})",
    "➕ Add Doctor",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: ACTIVE DOCTORS
# ══════════════════════════════════════════════════════════════════════════════
with tab_active:
    st.subheader("📋 Active Doctor Contacts")

    # Filters
    fcol1, fcol2, fcol3 = st.columns([2, 2, 2])
    with fcol1:
        search_active = st.text_input("🔍 Search Active Doctors", placeholder="Name, mobile, city, or clinic...", key="search_active")
    with fcol2:
        filter_spec_active = st.selectbox("Filter Specialty", ["All"] + SPECIALTIES, key="spec_active")
    with fcol3:
        filter_status_active = st.selectbox("Filter Status", ["All", "active", "paused", "completed"], key="stat_active")

    # Apply filters locally on active_doctors
    filtered_active = active_doctors
    if search_active:
        s = search_active.strip().lower()
        filtered_active = [
            d for d in filtered_active
            if s in d["name"].lower()
            or s in d["mobile"].lower()
            or (d.get("city") and s in d["city"].lower())
            or (d.get("clinic_name") and s in d["clinic_name"].lower())
        ]
    if filter_spec_active != "All":
        filtered_active = [d for d in filtered_active if d["specialty"] == filter_spec_active]
    if filter_status_active != "All":
        filtered_active = [d for d in filtered_active if d["status"] == filter_status_active]

    if filtered_active:
        df = pd.DataFrame(filtered_active)
        display_cols = ["id", "name", "mobile", "specialty", "clinic_name", "city", "status", "created_at"]
        df_display = df[display_cols].copy()
        df_display["created_at"] = pd.to_datetime(df_display["created_at"]).dt.strftime("%Y-%m-%d")
        df_display.columns = ["ID", "Name", "Mobile", "Specialty", "Clinic", "City", "Status", "Added"]

        st.caption(f"Showing **{len(df_display)}** active doctor(s)")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        csv = df_display.to_csv(index=False)
        st.download_button("⬇️ Export Active Doctors (CSV)", csv, "active_doctors.csv", "text/csv")

        st.divider()

        # Doctor Actions & Management
        st.subheader("⚙️ Doctor Actions & Management")
        st.markdown("Select a doctor to update details, pause/resume pipelines, opt out, or delete records.")

        doctor_options = {
            f"[{d['id']}] Dr. {d['name']} — {d['specialty']} ({d['mobile']})": d
            for d in filtered_active
        }
        selected_label = st.selectbox("Select Doctor:", list(doctor_options.keys()), key="select_active_doc")
        selected_doc = doctor_options[selected_label]

        # Doctor Detail Card
        st.markdown(
            f"""
            <div style="background: rgba(30, 45, 69, 0.4); border: 1px solid #2d4a6e; border-radius: 10px; padding: 14px 18px; margin: 10px 0 16px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 1.25rem; font-weight: 700; color: #60a5fa;">Dr. {selected_doc['name']}</span>
                        <span style="background: #1e3a5f; color: #93c5fd; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 8px;">{selected_doc['specialty']}</span>
                        <span style="background: {'#166534' if selected_doc['status'] == 'active' else '#854d0e'}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 6px;">Status: {selected_doc['status']}</span>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">ID: #{selected_doc['id']}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 10px; font-size: 0.95rem;">
                    <div>📱 <strong>Mobile:</strong> <code>{selected_doc['mobile']}</code></div>
                    <div>🏥 <strong>Clinic:</strong> {selected_doc.get('clinic_name') or 'N/A'}</div>
                    <div>📍 <strong>City:</strong> {selected_doc.get('city') or 'N/A'}</div>
                </div>
                {f'<div style="margin-top: 8px; color: #cbd5e1; font-size: 0.9rem;">📝 <strong>Notes:</strong> {selected_doc["notes"]}</div>' if selected_doc.get('notes') else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        bcol1, bcol2, bcol3, bcol4 = st.columns([1.2, 1.2, 1.2, 1.5])

        with bcol1:
            if st.button("✏️ Edit Doctor", key=f"edit_btn_{selected_doc['id']}", use_container_width=True):
                show_edit_dialog(selected_doc)

        with bcol2:
            if st.button("🚫 Opt Out Doctor", key=f"optout_btn_{selected_doc['id']}", use_container_width=True, help="Immediately exclude this doctor from all WhatsApp campaigns"):
                try:
                    api.post(f"/api/doctors/{selected_doc['id']}/opt-out")
                    st.success(f"Dr. {selected_doc['name']} has been opted out.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Opt-out failed: {e}")

        with bcol3:
            if st.button("🗑️ Delete Doctor", key=f"del_btn_{selected_doc['id']}", type="secondary", use_container_width=True, help="Permanently delete doctor record"):
                show_delete_dialog(selected_doc)

        with bcol4:
            if selected_doc["status"] == "active":
                if st.button("⏸️ Pause Outreach", key=f"pause_btn_{selected_doc['id']}", use_container_width=True):
                    try:
                        api.post(f"/api/doctors/{selected_doc['id']}/pause", json={"reason": "Manual pause from Doctor Management"})
                        st.info(f"Outreach paused for Dr. {selected_doc['name']}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error pausing: {e}")
            elif selected_doc["status"] == "paused":
                if st.button("▶️ Resume Outreach", key=f"resume_btn_{selected_doc['id']}", use_container_width=True):
                    try:
                        api.post(f"/api/doctors/{selected_doc['id']}/resume")
                        st.success(f"Outreach resumed for Dr. {selected_doc['name']}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error resuming: {e}")
            else:
                st.caption(f"Pipeline status: **{selected_doc['status']}**")

    else:
        st.info("No active doctors found matching the current filters.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: OPTED-OUT DOCTORS
# ══════════════════════════════════════════════════════════════════════════════
with tab_opted_out:
    st.subheader("🚫 Opted-Out Doctors")

    st.info(
        "🛡️ **Outreach Safety Guarantee:** Doctors listed here have opted out of communications. "
        "They are completely excluded from WhatsApp messages, automated drip sequences, and manual sending queues. "
        "You can inspect their past records, update contact details, or opt them back in when requested.",
        icon="ℹ️",
    )

    search_optout = st.text_input("🔍 Search Opted-Out Doctors", placeholder="Name, mobile, city, or clinic...", key="search_optout")

    filtered_optout = opted_out_doctors
    if search_optout:
        so = search_optout.strip().lower()
        filtered_optout = [
            d for d in filtered_optout
            if so in d["name"].lower()
            or so in d["mobile"].lower()
            or (d.get("city") and so in d["city"].lower())
            or (d.get("clinic_name") and so in d["clinic_name"].lower())
        ]

    if filtered_optout:
        df_opt = pd.DataFrame(filtered_optout)
        cols_opt = ["id", "name", "mobile", "specialty", "clinic_name", "city", "updated_at"]
        df_opt_display = df_opt[cols_opt].copy()
        df_opt_display["updated_at"] = pd.to_datetime(df_opt_display["updated_at"]).dt.strftime("%Y-%m-%d")
        df_opt_display.columns = ["ID", "Name", "Mobile", "Specialty", "Clinic", "City", "Opted Out Since"]

        st.caption(f"Showing **{len(df_opt_display)}** opted-out doctor(s)")
        st.dataframe(df_opt_display, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("⚙️ Manage Opted-Out Doctor")
        optout_options = {
            f"[{d['id']}] Dr. {d['name']} — {d['specialty']} ({d['mobile']})": d
            for d in filtered_optout
        }
        selected_optout_label = st.selectbox("Select Opted-Out Doctor:", list(optout_options.keys()), key="select_optout_doc")
        selected_optout_doc = optout_options[selected_optout_label]

        # Opted-out Doctor Card
        st.markdown(
            f"""
            <div style="background: rgba(80, 20, 20, 0.25); border: 1px solid #7f1d1d; border-radius: 10px; padding: 14px 18px; margin: 10px 0 16px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 1.25rem; font-weight: 700; color: #f87171;">Dr. {selected_optout_doc['name']}</span>
                        <span style="background: #7f1d1d; color: #fecaca; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 8px;">OPTED OUT</span>
                        <span style="background: #1e293b; color: #94a3b8; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 6px;">{selected_optout_doc['specialty']}</span>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">ID: #{selected_optout_doc['id']}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 10px; font-size: 0.95rem;">
                    <div>📱 <strong>Mobile:</strong> <code>{selected_optout_doc['mobile']}</code></div>
                    <div>🏥 <strong>Clinic:</strong> {selected_optout_doc.get('clinic_name') or 'N/A'}</div>
                    <div>📍 <strong>City:</strong> {selected_optout_doc.get('city') or 'N/A'}</div>
                </div>
                {f'<div style="margin-top: 8px; color: #cbd5e1; font-size: 0.9rem;">📝 <strong>Notes:</strong> {selected_optout_doc["notes"]}</div>' if selected_optout_doc.get('notes') else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        ocol1, ocol2, ocol3 = st.columns([1.5, 1.2, 1.2])

        with ocol1:
            if st.button("✅ Opt Back In", key=f"optin_btn_{selected_optout_doc['id']}", type="primary", use_container_width=True, help="Re-activate doctor and resume pipeline outreach"):
                try:
                    res = api.post(f"/api/doctors/{selected_optout_doc['id']}/opt-in")
                    st.success(f"✅ Dr. {res['name']} has been opted back in and re-enrolled in outreach!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Opt-in failed: {e}")

        with ocol2:
            if st.button("✏️ Edit Details", key=f"edit_optout_btn_{selected_optout_doc['id']}", use_container_width=True):
                show_edit_dialog(selected_optout_doc)

        with ocol3:
            if st.button("🗑️ Delete Doctor", key=f"del_optout_btn_{selected_optout_doc['id']}", type="secondary", use_container_width=True):
                show_delete_dialog(selected_optout_doc)

    else:
        st.success("🎉 No doctors are currently opted out! All contacts are active in the sales pipeline.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: ADD DOCTOR
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.subheader("➕ Add New Doctor")
    st.markdown("Register a new doctor contact. They will automatically be enrolled in their specialty's outreach pipeline.")

    with st.form("add_doctor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *", placeholder="Dr. Ramesh Kumar")
            mobile = st.text_input(
                "WhatsApp Number (with country code) *",
                placeholder="+919876543210",
                help="Include country code, e.g. +91 for India, +1 for US.",
            )
            specialty = st.selectbox("Specialty *", SPECIALTIES)
        with col2:
            clinic = st.text_input("Clinic / Hospital Name", placeholder="City Hospital")
            city = st.text_input("City", placeholder="Mumbai")
            notes = st.text_area("Notes", placeholder="Any additional notes…", height=100)

        submitted = st.form_submit_button("➕ Add Doctor & Enrol in Pipeline", type="primary", use_container_width=True)

        if submitted:
            clean_name = name.strip()
            clean_mobile = mobile.strip().replace(" ", "").replace("-", "")

            if not clean_name:
                st.error("Name is required.")
            elif not clean_mobile:
                st.error("Mobile number is required.")
            elif not clean_mobile.startswith("+") or not clean_mobile[1:].isdigit():
                st.error("Mobile number must include a country code starting with '+' (e.g. +919876543210).")
            elif len(clean_mobile[1:]) < 10:
                st.error("Mobile number must have at least 10 digits after the country code.")
            else:
                try:
                    result = api.post("/api/doctors", json={
                        "name": clean_name,
                        "mobile": clean_mobile,
                        "specialty": specialty,
                        "clinic_name": clinic.strip() or None,
                        "city": city.strip() or None,
                        "notes": notes.strip() or None,
                    })
                    st.success(
                        f"✅ **Dr. {result['name']}** added and enrolled in the "
                        f"**{result['specialty']}** pipeline!"
                    )
                    st.rerun()
                except Exception as e:
                    err_msg = str(e)
                    if "already exists" in err_msg:
                        st.error(f"❌ Duplicate Mobile: A doctor with mobile `{clean_mobile}` is already registered in the system.")
                    else:
                        st.error(f"❌ Error adding doctor: {e}")

