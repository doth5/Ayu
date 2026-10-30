"""
Send Messages page - Bulk WhatsApp Outreach & Daily Pipeline Queue.

Features:
1. Bulk Outreach Campaigns:
   - Searchable, filterable doctor list with Select All & count indicator
   - Auto-exclusion of opted-out doctors
   - Multiple message types: Text, Images, PDF documents, Videos, DOCX files, Links
   - Sequential sending with 10-20s configurable delay
   - Live campaign monitor with Progress bar, Pause, Resume, and Cancel
   - Persistent per-recipient status (Pending, Sending, Sent, Failed, Skipped)
2. Daily Outreach Pipeline Queue:
   - Prepare due messages, preview templates/media, manual links & statuses
"""
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from app.streamlit.utils import api_client as api

st.set_page_config(page_title="Send Messages – AyuSynk", page_icon="📤", layout="wide")

# ── Custom CSS for Badges & Layout ───────────────────────────────────────────
st.markdown(
    """
<style>
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}
.badge-pending {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid #f59e0b;
}
.badge-sending {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    border: 1px solid #3b82f6;
    animation: pulse 1.5s infinite;
}
.badge-sent {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid #10b981;
}
.badge-failed {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid #ef4444;
}
.badge-skipped {
    background: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
    border: 1px solid #64748b;
}
@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
}
.metric-box {
    background: linear-gradient(135deg, #1e2d45 0%, #172338 100%);
    border: 1px solid #2d4a6e;
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}
.metric-val {
    font-size: 1.8rem;
    font-weight: 700;
    color: #60a5fa;
}
.metric-lbl {
    font-size: 0.8rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 2px;
}
.card-header-doc {
    font-size: 1.05rem;
    font-weight: 600;
    color: #e2e8f0;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="page-header">
  <h1>📤 Send Messages & Bulk Outreach</h1>
  <p>Deliver targeted campaigns sequentially to selected doctors or work through your daily automated pipeline queue.</p>
</div>
""",
    unsafe_allow_html=True,
)

# WhatsApp connection status check
try:
    wa_status = api.get("/api/executions/whatsapp-web-status")
    session_ok = wa_status.get("session_files_exist", False)
    browser_active = wa_status.get("browser_open", False)
except Exception:
    session_ok = False
    browser_active = False

with st.sidebar:
    st.markdown("### 📱 WhatsApp Session")
    if browser_active and session_ok:
        st.success("🟢 WhatsApp Web Ready", icon="✅")
        st.caption("Chromium is open and logged in. Campaigns will send automatically.")
    elif browser_active and not session_ok:
        st.warning("🟡 Browser Open — QR Scan Needed", icon="📱")
        st.caption("Chromium is open. Please scan the QR code to link WhatsApp.")
    elif session_ok and not browser_active:
        st.info("🔵 Session Saved — Browser Starting…", icon="⏳")
        st.caption("WhatsApp is launching in the background. Ready shortly.")
    else:
        st.warning("🟡 WhatsApp Not Linked", icon="⚠️")
        st.caption("Click below to open the browser and scan the QR code.")

    st.divider()
    if st.button("🔗 Open WhatsApp / Scan QR", use_container_width=True, type="primary"):
        try:
            with st.spinner("Launching WhatsApp Web browser..."):
                res = api.post("/api/executions/whatsapp-web-setup", params={"timeout_seconds": 120})
            status = res.get("status", "")
            if status == "already_logged_in":
                st.success("✅ Already logged in and ready!")
            elif status == "logged_in":
                st.success("✅ QR scanned successfully! Ready to send.")
            elif status == "timeout":
                st.warning("⏰ QR not scanned in time. Try again.")
            else:
                st.info(res.get("message", "Browser launched!"))
        except Exception as e:
            st.error(f"Setup error: {e}")


# ── Main Tabs ─────────────────────────────────────────────────────────────────
# ── Active tab tracking (switch to monitor after campaign launch) ────────────
if "active_tab_index" not in st.session_state:
    st.session_state.active_tab_index = 0

tab_bulk, tab_monitor, tab_queue, tab_history = st.tabs(
    [
        "🚀 Bulk Outreach Campaign",
        "📡 Live Campaign Monitor",
        "📬 Pipeline Outreach Queue",
        "📜 Campaign History",
    ]
)

# Auto-switch to Live Monitor tab after a campaign is launched
if st.session_state.get("active_tab_index", 0) == 1:
    st.session_state.active_tab_index = 0  # reset so it doesn't loop
    st.markdown(
        """
        <script>
        (function() {
            // Click the second tab (Live Campaign Monitor) after the page renders
            const tryClick = (attempts) => {
                const tabs = window.parent.document.querySelectorAll(
                    'button[role="tab"], [data-baseweb="tab"]'
                );
                if (tabs.length >= 2) {
                    tabs[1].click();
                } else if (attempts > 0) {
                    setTimeout(() => tryClick(attempts - 1), 300);
                }
            };
            setTimeout(() => tryClick(10), 500);
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

# ==============================================================================
# TAB 1: 🚀 BULK OUTREACH CAMPAIGN
# ==============================================================================
with tab_bulk:
    st.markdown("### 🎯 Create & Launch Bulk Campaign")
    st.caption(
        "Select recipients, build your message (text, document, photo, video, or link), "
        "and send sequentially with a random human-like delay (10–20s) to keep your WhatsApp account safe."
    )

    # ── Step 1: Select Doctors ────────────────────────────────────────────────
    st.markdown("#### 1️⃣ Select Doctors")

    # Load active, non-opted-out doctors
    try:
        all_doctors = api.get("/api/doctors", opted_out=False)
    except Exception as e:
        st.error(f"Could not load doctors: {e}")
        all_doctors = []

    if not all_doctors:
        st.warning("⚠️ No active doctors found. Add doctors in the Doctor Management page first.")
    else:
        # Search & Filters
        fcol1, fcol2 = st.columns([2, 1])
        with fcol1:
            search_query = st.text_input(
                "🔍 Search doctors",
                placeholder="Search by name, mobile, clinic, or city...",
                key="bulk_search",
            ).strip().lower()
        with fcol2:
            specialties = sorted(list({d.get("specialty", "") for d in all_doctors if d.get("specialty")}))
            spec_filter = st.selectbox("Filter by Specialty", ["All"] + specialties, key="bulk_spec")

        # Filtered list
        filtered_docs = []
        for d in all_doctors:
            if spec_filter != "All" and d.get("specialty") != spec_filter:
                continue
            if search_query:
                haystack = f"{d.get('name', '')} {d.get('mobile', '')} {d.get('clinic_name', '')} {d.get('city', '')}".lower()
                if search_query not in haystack:
                    continue
            filtered_docs.append(d)

        # Select All / Clear All controls
        if "selected_doc_ids" not in st.session_state:
            st.session_state.selected_doc_ids = set()

        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
        with btn_col1:
            if st.button("☑️ Select All Visible", key="select_all_btn"):
                for d in filtered_docs:
                    st.session_state.selected_doc_ids.add(d["id"])
                st.rerun()
        with btn_col2:
            if st.button("⬜ Clear Selection", key="clear_all_btn"):
                st.session_state.selected_doc_ids.clear()
                st.rerun()
        with btn_col3:
            st.info(
                f"**🎯 {len(st.session_state.selected_doc_ids)} doctor(s) selected** "
                f"out of {len(all_doctors)} active contacts. *(Opted-out doctors are automatically excluded)*",
                icon="👥",
            )

        # Doctor Selection Table / Checkboxes
        st.markdown(
            """
            <div style="font-size:0.85rem;color:#94a3b8;margin-bottom:8px;">
            Check the doctors you wish to include in this campaign:
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(height=260):
            for doc in filtered_docs:
                is_selected = doc["id"] in st.session_state.selected_doc_ids
                c_chk, c_name, c_spec, c_city, c_phone = st.columns([0.6, 2.5, 2, 1.5, 1.8])
                with c_chk:
                    checked = st.checkbox(
                        label=f"select_{doc['id']}",
                        value=is_selected,
                        key=f"chk_doc_{doc['id']}",
                        label_visibility="collapsed",
                    )
                    if checked and not is_selected:
                        st.session_state.selected_doc_ids.add(doc["id"])
                    elif not checked and is_selected:
                        st.session_state.selected_doc_ids.discard(doc["id"])
                with c_name:
                    st.markdown(f"**Dr. {doc['name']}**")
                with c_spec:
                    st.markdown(f"<span class='specialty-badge'>{doc['specialty']}</span>", unsafe_allow_html=True)
                with c_city:
                    st.caption(doc.get("city") or "—")
                with c_phone:
                    st.code(doc["mobile"], language=None)

    st.divider()

    # ── Step 2: Message Content ───────────────────────────────────────────────
    st.markdown("#### 2️⃣ Compose Message & Attachment")

    c_type_col, c_name_col = st.columns([1, 2])
    with c_type_col:
        msg_type = st.selectbox(
            "Message Type",
            [
                "Text Only",
                "PDF Document",
                "Image / Photo",
                "Video",
                "DOCX Document",
                "Web Link & Pitch",
            ],
            key="bulk_msg_type",
        )
    with c_name_col:
        campaign_name = st.text_input(
            "Campaign Name",
            value=f"Outreach Campaign – {datetime.now().strftime('%b %d, %H:%M')}",
            key="bulk_campaign_name",
        )

    uploaded_file_path = None
    uploaded_file_name = None
    caption_text = None
    body_text = None

    if msg_type == "Text Only":
        body_text = st.text_area(
            "Message Text",
            placeholder="Type your WhatsApp pitch or message here...",
            height=140,
            key="bulk_text_body",
        )
        st.caption(f"Characters: {len(body_text) if body_text else 0}")

    elif msg_type == "Image / Photo":
        img_file = st.file_uploader(
            "Upload Image (JPG, PNG, WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            key="bulk_img_upload",
        )
        if img_file:
            save_dir = ROOT / "media" / "campaigns"
            save_dir.mkdir(parents=True, exist_ok=True)
            saved_name = f"{uuid.uuid4().hex[:8]}_{img_file.name}"
            saved_p = save_dir / saved_name
            saved_p.write_bytes(img_file.getbuffer())
            uploaded_file_path = str(saved_p)
            uploaded_file_name = img_file.name
            st.image(str(saved_p), width=260, caption=f"Preview: {img_file.name}")

        caption_text = st.text_area(
            "Image Caption (Optional)",
            placeholder="Add an optional caption that will appear with the image...",
            height=80,
            key="bulk_img_caption",
        )

    elif msg_type == "PDF Document":
        pdf_file = st.file_uploader(
            "Upload PDF File",
            type=["pdf"],
            key="bulk_pdf_upload",
        )
        if pdf_file:
            save_dir = ROOT / "media" / "campaigns"
            save_dir.mkdir(parents=True, exist_ok=True)
            saved_name = f"{uuid.uuid4().hex[:8]}_{pdf_file.name}"
            saved_p = save_dir / saved_name
            saved_p.write_bytes(pdf_file.getbuffer())
            uploaded_file_path = str(saved_p)
            uploaded_file_name = pdf_file.name
            st.success(f"📎 PDF Loaded: **{pdf_file.name}** ({round(pdf_file.size / 1024, 1)} KB)")

        caption_text = st.text_area(
            "Document Note / Caption (Optional)",
            placeholder="Note or text to send with the PDF...",
            height=80,
            key="bulk_pdf_caption",
        )

    elif msg_type == "Video":
        vid_file = st.file_uploader(
            "Upload Video File (MP4, MOV)",
            type=["mp4", "mov", "webm", "m4v"],
            key="bulk_vid_upload",
        )
        if vid_file:
            save_dir = ROOT / "media" / "campaigns"
            save_dir.mkdir(parents=True, exist_ok=True)
            saved_name = f"{uuid.uuid4().hex[:8]}_{vid_file.name}"
            saved_p = save_dir / saved_name
            saved_p.write_bytes(vid_file.getbuffer())
            uploaded_file_path = str(saved_p)
            uploaded_file_name = vid_file.name
            st.video(str(saved_p))

        caption_text = st.text_area(
            "Video Caption (Optional)",
            placeholder="Add an optional caption sent with the video...",
            height=80,
            key="bulk_vid_caption",
        )

    elif msg_type == "DOCX Document":
        doc_file = st.file_uploader(
            "Upload Word Document (DOCX, DOC)",
            type=["docx", "doc"],
            key="bulk_docx_upload",
        )
        if doc_file:
            save_dir = ROOT / "media" / "campaigns"
            save_dir.mkdir(parents=True, exist_ok=True)
            saved_name = f"{uuid.uuid4().hex[:8]}_{doc_file.name}"
            saved_p = save_dir / saved_name
            saved_p.write_bytes(doc_file.getbuffer())
            uploaded_file_path = str(saved_p)
            uploaded_file_name = doc_file.name
            st.success(f"📄 Document Loaded: **{doc_file.name}** ({round(doc_file.size / 1024, 1)} KB)")

        caption_text = st.text_area(
            "Document Message (Optional)",
            placeholder="Accompanying text message...",
            height=80,
            key="bulk_docx_caption",
        )

    elif msg_type == "Web Link & Pitch":
        target_link = st.text_input(
            "Destination URL / Link",
            placeholder="e.g. https://ayudevices.com/ayusynk-demo",
            key="bulk_link_url",
        ).strip()
        link_pitch = st.text_area(
            "Intro Message / Pitch",
            placeholder="Doctor, check out this live demo of the AyuSynk digital stethoscope:",
            height=100,
            key="bulk_link_pitch",
        )
        if target_link:
            body_text = f"{link_pitch.strip()}\n\n🔗 {target_link}" if link_pitch.strip() else target_link
        else:
            body_text = link_pitch

    st.divider()

    # ── Step 3: Sequential Sending Safety Settings ───────────────────────────
    st.markdown("#### 3️⃣ Sequential Delivery & Pacing Controls")
    st.info(
        "🛡️ **Safety Assurance:** Messages are sent to **strictly one doctor at a time**. "
        "After each send, the worker pauses for a randomized duration between Min Delay and Max Delay "
        "to simulate natural human pacing and prevent spam detection.",
        icon="⏱️",
    )

    d_col1, d_col2, d_col3 = st.columns([1, 1, 2])
    with d_col1:
        min_delay = st.number_input(
            "Min Delay (seconds)",
            min_value=5,
            max_value=60,
            value=10,
            step=1,
            help="Minimum seconds to wait after sending to a recipient",
        )
    with d_col2:
        max_delay = st.number_input(
            "Max Delay (seconds)",
            min_value=min_delay,
            max_value=120,
            value=max(20, min_delay),
            step=1,
            help="Maximum seconds to wait after sending to a recipient",
        )
    with d_col3:
        num_recipients = len(st.session_state.selected_doc_ids)
        if num_recipients > 0:
            est_sec_min = num_recipients * min_delay
            est_sec_max = num_recipients * max_delay
            st.metric(
                "Estimated Duration",
                f"~{round(est_sec_min / 60, 1)} – {round(est_sec_max / 60, 1)} min",
                f"{num_recipients} recipients",
            )
        else:
            st.metric("Estimated Duration", "0 min", "0 recipients")

    st.divider()

    # ── Step 4: Launch Campaign ───────────────────────────────────────────────
    st.markdown("#### 4️⃣ Launch Campaign")
    ready_to_launch = True
    error_reasons = []

    if not st.session_state.selected_doc_ids:
        ready_to_launch = False
        error_reasons.append("Select at least one doctor above.")

    if msg_type == "Text Only" and not (body_text and body_text.strip()):
        ready_to_launch = False
        error_reasons.append("Enter message text.")

    if msg_type in ("Image / Photo", "PDF Document", "Video", "DOCX Document") and not uploaded_file_path:
        ready_to_launch = False
        error_reasons.append(f"Upload a file for {msg_type}.")

    if msg_type == "Web Link & Pitch" and not (body_text and body_text.strip()):
        ready_to_launch = False
        error_reasons.append("Provide a destination link or message.")

    if error_reasons:
        st.warning("⚠️ Ready to launch checklist: " + " • ".join(error_reasons))

    if st.button("🚀 Start Bulk Campaign", type="primary", disabled=not ready_to_launch, use_container_width=True):
        try:
            # Map type to internal type
            type_map = {
                "Text Only": "text",
                "Image / Photo": "image",
                "PDF Document": "pdf",
                "Video": "video",
                "DOCX Document": "docx",
                "Web Link & Pitch": "link",
            }

            payload = {
                "name": campaign_name.strip(),
                "message_type": type_map.get(msg_type, "text"),
                "text_message": body_text or None,
                "caption": caption_text or None,
                "file_path": uploaded_file_path,
                "file_name": uploaded_file_name,
                "delay_min": int(min_delay),
                "delay_max": int(max_delay),
                "doctor_ids": list(st.session_state.selected_doc_ids),
            }

            # 1. Create campaign
            created = api.post("/api/campaigns", json=payload)
            camp_id = created["id"]

            # 2. Ensure WhatsApp browser is open & launch campaign worker
            try:
                api.post("/api/executions/whatsapp-web-setup")
            except Exception:
                pass
            api.post(f"/api/campaigns/{camp_id}/start")

            st.session_state.active_campaign_id = camp_id
            st.session_state.active_tab_index = 1  # switch to Live Monitor tab
            st.success(f"🎉 Campaign #{camp_id} ('{campaign_name}') started! Opening Live Monitor...")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"Error launching campaign: {e}")


# ==============================================================================
# TAB 2: 📡 LIVE CAMPAIGN MONITOR & CONTROLS
# ==============================================================================
with tab_monitor:
    st.markdown("### 📡 Live Campaign Monitor & Controls")

    # Fetch campaigns list for dropdown
    try:
        all_campaigns = api.get("/api/campaigns")
    except Exception as e:
        st.error(f"Error loading campaigns: {e}")
        all_campaigns = []

    if not all_campaigns:
        st.info("No campaigns found yet. Create your first campaign in the 'Bulk Outreach Campaign' tab!")
    else:
        # Determine which campaign to display
        camp_options = {c["id"]: f"#{c['id']} — {c['name']} [{c['status'].upper()}]" for c in all_campaigns}
        default_id = getattr(st.session_state, "active_campaign_id", None)
        if default_id not in camp_options:
            default_id = all_campaigns[0]["id"]

        selected_camp_id = st.selectbox(
            "Select Campaign to Monitor",
            options=list(camp_options.keys()),
            format_func=lambda cid: camp_options[cid],
            index=list(camp_options.keys()).index(default_id) if default_id in camp_options else 0,
            key="monitor_camp_select",
        )

        try:
            camp = api.get(f"/api/campaigns/{selected_camp_id}")
        except Exception as e:
            st.error(f"Failed to fetch campaign details: {e}")
            camp = None

        if camp:
            st.session_state.active_campaign_id = camp["id"]
            status = camp["status"]
            total = camp["total_recipients"]
            sent = camp["sent_count"]
            failed = camp["failed_count"]
            skipped = camp["skipped_count"]
            done_count = sent + failed + skipped
            progress_pct = (done_count / total) if total > 0 else 0.0

            # Status Banner & Control Buttons Row
            status_colors = {
                "running": "badge-sending",
                "paused": "badge-pending",
                "completed": "badge-sent",
                "cancelled": "badge-failed",
                "draft": "badge-pending",
            }
            badge_cls = status_colors.get(status, "badge-pending")

            hdr_col, btn_pause, btn_resume, btn_cancel, btn_refresh = st.columns([3, 1, 1, 1, 1])

            with hdr_col:
                st.markdown(
                    f"### {camp['name']} <span class='badge {badge_cls}'>{status}</span>",
                    unsafe_allow_html=True,
                )
                if camp.get("file_name"):
                    st.caption(f"📎 Attachment: `{camp['file_name']}` | Pacing: {camp['delay_min']}–{camp['delay_max']}s")
                elif camp.get("text_message"):
                    preview_txt = camp['text_message'][:80] + ("..." if len(camp['text_message']) > 80 else "")
                    st.caption(f"📝 Message: *\"{preview_txt}\"* | Pacing: {camp['delay_min']}–{camp['delay_max']}s")

            with btn_pause:
                if status == "running":
                    if st.button("⏸️ Pause", key=f"pause_{camp['id']}", use_container_width=True):
                        try:
                            api.post(f"/api/campaigns/{camp['id']}/pause")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            with btn_resume:
                if status in ("paused", "draft"):
                    if st.button("▶️ Resume", key=f"resume_{camp['id']}", type="primary", use_container_width=True):
                        try:
                            api.post(f"/api/campaigns/{camp['id']}/resume")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            with btn_cancel:
                if status in ("running", "paused"):
                    if st.button("🛑 Cancel", key=f"cancel_{camp['id']}", use_container_width=True):
                        try:
                            api.post(f"/api/campaigns/{camp['id']}/cancel")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            with btn_refresh:
                if st.button("🔄 Refresh", key=f"refresh_{camp['id']}", use_container_width=True):
                    st.rerun()

            # Progress Bar & Metric Counters
            st.progress(progress_pct, text=f"Progress: {done_count} of {total} completed ({int(progress_pct * 100)}%)")

            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                st.markdown(
                    f"<div class='metric-box'><div class='metric-val'>{total}</div><div class='metric-lbl'>Total Recipients</div></div>",
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    f"<div class='metric-box'><div class='metric-val' style='color:#34d399;'>{sent}</div><div class='metric-lbl'>Sent Successfully</div></div>",
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    f"<div class='metric-box'><div class='metric-val' style='color:#f87171;'>{failed}</div><div class='metric-lbl'>Failed</div></div>",
                    unsafe_allow_html=True,
                )
            with m4:
                st.markdown(
                    f"<div class='metric-box'><div class='metric-val' style='color:#94a3b8;'>{skipped}</div><div class='metric-lbl'>Skipped / Opted-Out</div></div>",
                    unsafe_allow_html=True,
                )
            with m5:
                pending_cnt = max(0, total - done_count)
                st.markdown(
                    f"<div class='metric-box'><div class='metric-val' style='color:#fbbf24;'>{pending_cnt}</div><div class='metric-lbl'>Remaining</div></div>",
                    unsafe_allow_html=True,
                )

            st.write("")

            # Retry Failed Doctors Option
            recipients = camp.get("recipients", [])
            failed_recipients = [r for r in recipients if r["status"] == "failed"]
            if failed_recipients and status in ("completed", "paused", "cancelled"):
                st.warning(
                    f"⚠️ {len(failed_recipients)} recipient(s) failed in this campaign. "
                    "You can create a targeted retry campaign for only the failed doctors with one click."
                )
                if st.button(f"🔁 Retry {len(failed_recipients)} Failed Doctor(s)", type="secondary"):
                    try:
                        retry_payload = {
                            "name": f"Retry: {camp['name']}",
                            "message_type": camp["message_type"],
                            "text_message": camp.get("text_message"),
                            "caption": camp.get("caption"),
                            "file_path": camp.get("file_path"),
                            "file_name": camp.get("file_name"),
                            "delay_min": camp.get("delay_min", 10),
                            "delay_max": camp.get("delay_max", 20),
                            "doctor_ids": [r["doctor_id"] for r in failed_recipients],
                        }
                        retried = api.post("/api/campaigns", json=retry_payload)
                        api.post(f"/api/campaigns/{retried['id']}/start")
                        st.session_state.active_campaign_id = retried["id"]
                        st.success(f"Retrying failed recipients in Campaign #{retried['id']}!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error initiating retry: {e}")

            # Recipient Details Table
            st.markdown("#### 📋 Recipient Live Status")
            if not recipients:
                st.caption("No recipient records found.")
            else:
                for idx, r in enumerate(recipients, 1):
                    r_status = r["status"]
                    badge_type = {
                        "sent": "badge-sent",
                        "sending": "badge-sending",
                        "pending": "badge-pending",
                        "failed": "badge-failed",
                        "skipped": "badge-skipped",
                    }.get(r_status, "badge-pending")

                    with st.container():
                        col_idx, col_name, col_mobile, col_stat, col_time = st.columns([0.4, 2.5, 2, 1.5, 2.5])
                        with col_idx:
                            st.caption(f"#{idx}")
                        with col_name:
                            st.markdown(f"**Dr. {r['doctor_name']}**")
                        with col_mobile:
                            st.code(r["mobile"], language=None)
                        with col_stat:
                            st.markdown(f"<span class='badge {badge_type}'>{r_status}</span>", unsafe_allow_html=True)
                        with col_time:
                            if r.get("sent_at"):
                                sent_dt = datetime.fromisoformat(r["sent_at"].replace("Z", "+00:00"))
                                st.caption(f"🕒 {sent_dt.strftime('%H:%M:%S')}")
                            elif r.get("error_message"):
                                st.caption(f"❌ {r['error_message'][:60]}")
                            elif r_status == "sending":
                                st.caption("⏳ Sending now...")
                            else:
                                st.caption("In Queue")
                        st.divider()

            # Auto-refresh if campaign is currently running
            if status == "running":
                st.caption("⚡ Campaign is actively sending in the background. Auto-refreshing in 4 seconds...")
                time.sleep(4)
                st.rerun()


# ==============================================================================
# TAB 3: 📬 PIPELINE OUTREACH QUEUE
# ==============================================================================
with tab_queue:
    st.markdown("### 📬 Daily Pipeline Outreach Queue")
    st.caption("Step-by-step outreach sequences scheduled automatically by the pipeline engine.")

    col_prepare, col_info = st.columns([2, 3])
    with col_prepare:
        if st.button("⚡ Prepare Due Messages", use_container_width=True, type="primary"):
            try:
                result = api.post("/api/executions/prepare-due")
                st.success(f"✅ {result.get('prepared', 0)} new message(s) prepared.")
                st.rerun()
            except Exception as e:
                st.error(f"Error preparing messages: {e}")
    with col_info:
        st.info(
            "Click **Prepare Due Messages** to calculate which messages are due today "
            "based on enrolled doctor delays. The background scheduler also checks this every 15 minutes.",
            icon="ℹ️",
        )

    st.divider()

    try:
        messages = api.get("/api/executions/prepared")
    except Exception as e:
        st.error(f"Could not load prepared messages: {e}")
        messages = []

    if not messages:
        st.markdown(
            """
            <div style="text-align:center;padding:48px;color:#475569;">
              <div style="font-size:3rem;">✅</div>
              <div style="font-size:1.2rem;font-weight:600;margin-top:8px;">All caught up!</div>
              <div style="margin-top:4px;">No pipeline messages pending right now. Check back later or prepare more above.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.subheader(f"📬 {len(messages)} Message(s) Ready to Send")

        for msg in messages:
            with st.expander(
                f"🩺 Dr. {msg['doctor_name']} — {msg['step_name']} ({msg['mobile']})",
                expanded=True,
            ):
                col_msg, col_actions = st.columns([3, 1])

                with col_msg:
                    if msg.get("message"):
                        st.markdown("**📝 Message:**")
                        st.code(msg["message"], language=None)

                    if msg.get("media_path"):
                        st.markdown(f"**📎 Attachment:** `{msg['media_path']}`")
                        p = Path(msg["media_path"])
                        if p.exists() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                            st.image(str(p), width=300)

                with col_actions:
                    st.markdown(f"**📱 {msg['mobile']}**")

                    # WhatsApp web prefilled link
                    if msg.get("wa_link"):
                        st.markdown(
                            f'<a href="{msg["wa_link"]}" target="_blank" class="wa-btn">📲 Open WhatsApp</a>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("<br>", unsafe_allow_html=True)

                    # Mark as sent
                    if st.button("✅ Mark as Sent", key=f"queue_sent_{msg['execution_id']}"):
                        try:
                            api.post(f"/api/executions/{msg['execution_id']}/mark-sent")
                            st.success("Marked as sent!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

                    # Mark as failed
                    if st.button("❌ Mark Failed", key=f"queue_fail_{msg['execution_id']}"):
                        try:
                            api.post(
                                f"/api/executions/{msg['execution_id']}/mark-failed",
                                json={"error": "Manual failure"},
                            )
                            st.warning("Marked as failed.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    if st.button("🔄 Refresh Queue", key="refresh_queue_btn"):
        st.rerun()


# ==============================================================================
# TAB 4: 📜 CAMPAIGN HISTORY
# ==============================================================================
with tab_history:
    st.markdown("### 📜 Campaign History & Audit Log")
    st.caption("Complete history of all bulk outreach campaigns.")

    try:
        history_list = api.get("/api/campaigns")
    except Exception as e:
        st.error(f"Error fetching campaign history: {e}")
        history_list = []

    if not history_list:
        st.info("No past campaigns found.")
    else:
        for c in history_list:
            c_status = c["status"]
            b_class = {
                "sent": "badge-sent",
                "completed": "badge-sent",
                "running": "badge-sending",
                "paused": "badge-pending",
                "cancelled": "badge-failed",
                "draft": "badge-pending",
            }.get(c_status, "badge-pending")

            with st.expander(
                f"Campaign #{c['id']}: {c['name']} — [{c_status.upper()}] ({c['sent_count']}/{c['total_recipients']} Sent)"
            ):
                h1, h2, h3, h4 = st.columns(4)
                with h1:
                    st.markdown(f"**Type:** `{c['message_type'].upper()}`")
                    st.caption(f"Created: {c['created_at'][:19].replace('T', ' ')}")
                with h2:
                    st.markdown(f"**Status:** <span class='badge {b_class}'>{c_status}</span>", unsafe_allow_html=True)
                    st.caption(f"Pacing: {c['delay_min']}–{c['delay_max']}s")
                with h3:
                    st.markdown(f"**Results:** ✅ {c['sent_count']} / ❌ {c['failed_count']} / ⏭️ {c['skipped_count']}")
                with h4:
                    col_btn_view, col_btn_del = st.columns(2)
                    with col_btn_view:
                        if st.button("👁️ Monitor", key=f"hist_mon_{c['id']}"):
                            st.session_state.active_campaign_id = c["id"]
                            st.rerun()
                    with col_btn_del:
                        if c_status != "running":
                            if st.button("🗑️ Delete", key=f"hist_del_{c['id']}"):
                                try:
                                    api.delete(f"/api/campaigns/{c['id']}")
                                    st.success("Deleted campaign.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting: {e}")
                        else:
                            st.caption("Cannot delete active")

                if c.get("text_message"):
                    st.markdown("**Message:**")
                    st.code(c["text_message"], language=None)
                if c.get("file_name"):
                    st.markdown(f"**Attachment:** `{c['file_name']}` ({c.get('file_path')})")
                    if c.get("caption"):
                        st.caption(f"Caption: {c['caption']}")
