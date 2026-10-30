"""
WhatsApp Automation Setup & Control Page (Playwright WA Web & Meta API).
Guides the user through:
1. First-time WhatsApp Web QR linking (persistent profile saved in wa_session/)
2. Verifying login & session health
3. Sending test text messages and PDF attachments
4. Triggering auto-send for prepared pipeline messages
5. Session management (closing browser, resetting session to change phone)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import time
from app.streamlit.utils import api_client as api

st.set_page_config(page_title="WhatsApp Setup – AyuSynk", page_icon="📲", layout="wide")

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-header" style="margin-bottom: 24px;">
  <h1 style="display:flex;align-items:center;gap:12px;margin:0 0 8px 0;font-size:2rem;font-weight:700;">
    📲 WhatsApp Automation Setup
  </h1>
  <p style="color:#94a3b8;font-size:1rem;margin:0;">
    High-reliability, free WhatsApp outreach powered by Playwright browser automation. No third-party API costs.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Mode & Session Diagnostics ──────────────────────────────────────────────
status_data = {}
try:
    status_data = api.get("/api/executions/whatsapp-status")
except Exception:
    pass

mode = status_data.get("mode", "manual")
auto_active = status_data.get("auto_send_active", False)
wa_web_enabled = status_data.get("wa_web_enabled", True)

# Local session files check
from app.core.whatsapp_web import (
    wa_web_get_session_status,
    wa_web_open_for_setup,
    wa_web_is_logged_in,
    wa_web_close,
    wa_web_reset_session,
    wa_web_send_message,
)
from app.core.whatsapp import send_whatsapp_message
session_info = wa_web_get_session_status()
session_exists = session_info.get("session_files_exist", False)
browser_open = session_info.get("browser_open", False)

# ── Dynamic Status Banner ───────────────────────────────────────────────────
if mode == "wa_web":
    if session_exists:
        badge_color = "#10b981"
        badge_bg = "rgba(16, 185, 129, 0.12)"
        status_text = "WhatsApp Web Session Configured (Saved in wa_session/)"
        sub_text = "Your login session is saved permanently. Messages will dispatch automatically without re-scanning QR."
        icon = "🟢"
    else:
        badge_color = "#f59e0b"
        badge_bg = "rgba(245, 158, 11, 0.12)"
        status_text = "First-Time Setup Required: Scan QR Code"
        sub_text = "No saved WhatsApp session detected. Click 'Open WhatsApp Web for QR Scan' below to link your phone."
        icon = "🟡"

    st.markdown(f"""
    <div style="background:{badge_bg};border:1px solid {badge_color};border-radius:12px;
                padding:16px 22px;margin-bottom:24px;display:flex;align-items:center;gap:16px;">
      <div style="font-size:2rem;">{icon}</div>
      <div style="flex-grow:1;">
        <div style="font-weight:700;color:{badge_color};font-size:1.05rem;">{status_text}</div>
        <div style="color:#94a3b8;font-size:0.875rem;margin-top:2px;">{sub_text}</div>
      </div>
      <div style="text-align:right;">
        <span style="background:{'#10b981' if auto_active else '#64748b'};color:#fff;
                     padding:4px 12px;border-radius:20px;font-size:0.8rem;font-weight:600;">
          Auto-Send: {'ON' if auto_active else 'OFF'}
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)
elif mode == "meta_api":
    st.info("ℹ️ Currently in **Meta Business API** mode (Official WhatsApp Cloud API).")
else:
    st.warning("ℹ️ Currently in **Manual-Send** mode. Ensure `WA_WEB_ENABLED=true` in `.env` to enable browser automation.")

# ── Metrics Row ─────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Delivery Engine", "Playwright (WA Web)" if mode == "wa_web" else mode.upper())
with m2:
    st.metric("Session Saved", "✅ Yes" if session_exists else "❌ Not Yet")
with m3:
    st.metric("Browser Process", "🟢 Open" if browser_open else "⚪ Idle / Closed")
with m4:
    st.metric("Pipeline Auto-Send", "✅ Active" if auto_active else "🟡 Inactive")

st.divider()

# ── Main Tabs ───────────────────────────────────────────────────────────────
tab_setup, tab_test, tab_auto, tab_manage = st.tabs([
    "🚀 1. First-Time Setup Wizard",
    "🧪 2. Test Send (Text & PDF)",
    "⚡ 3. Pipeline Auto-Send",
    "⚙️ 4. Session & Troubleshooting",
])

# ══════════════════ TAB 1: FIRST-TIME SETUP WIZARD ══════════════════════════
with tab_setup:
    st.subheader("First-Time Setup: Link Your WhatsApp in 3 Easy Steps")
    st.markdown("""
    WhatsApp Web automation runs through a secure local Chromium browser.
    Once linked via QR code, **your login session is permanently cached in your project (`wa_session/`)**,
    so you do **NOT** need to scan the QR code again on future app launches.
    """)

    col_w1, col_w2 = st.columns([1.1, 0.9])

    with col_w1:
        st.markdown("""
        #### 📋 Setup Instructions:
        1. **Keep your phone nearby** with WhatsApp open.
        2. On your phone: Tap **Settings** (iOS) or **⋮ More Options** (Android) → **Linked Devices**.
        3. Tap **Link a Device** (unlock with fingerprint/FaceID if prompted).
        4. Click the **'Open WhatsApp Web for QR Scan'** button below.
        5. A browser window will open displaying the WhatsApp Web QR code.
        6. **Point your phone camera at the QR code on your computer screen.**
        7. Once linked, WhatsApp Web will load your chats and save your session!
        """)

        st.markdown("<br>", unsafe_allow_html=True)
        setup_btn = st.button(
            "🚀 Open WhatsApp Web for QR Scan",
            type="primary",
            use_container_width=True,
            help="Opens Chromium to web.whatsapp.com and waits for your phone to scan the QR code."
        )

        if setup_btn:
            with st.spinner("Opening browser window to web.whatsapp.com... Please scan the QR code on your screen!"):
                try:
                    result = wa_web_open_for_setup(qr_timeout_seconds=120)
                except Exception as exc:
                    result = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}

                status = result.get("status")
                msg = result.get("message", "")

                if status == "already_logged_in":
                    st.success(f"🎉 {msg}")
                elif status == "logged_in":
                    st.balloons()
                    st.success(f"✅ {msg}")
                    st.info("💡 Your session is safely stored in `wa_session/`. Head over to the **'Test Send'** tab to verify delivery!")
                elif status == "timeout":
                    st.warning(f"⏱️ {msg}")
                    st.info("Tip: Open Linked Devices on your phone first, then click the button again to scan.")
                else:
                    st.error(f"❌ Error during setup: {msg or 'Browser failed to open. Check terminal logs.'}")

    with col_w2:
        st.markdown("#### 🔍 Session Health Check")
        st.caption("Verify whether WhatsApp Web is currently logged in without needing to scan:")

        if st.button("🔎 Check WhatsApp Web Login Status", use_container_width=True):
            with st.spinner("Checking active WhatsApp Web session..."):
                logged_in = wa_web_is_logged_in()
                if logged_in:
                    st.success("✅ **Active & Logged In!** WhatsApp Web is ready to send messages and pitch decks.")
                else:
                    st.warning("⚠️ **Not Logged In.** Click 'Open WhatsApp Web for QR Scan' to link your device.")

        st.markdown("""
        ---
        #### 💡 Good to Know:
        - **Safe & Official:** Operates directly on WhatsApp Web without modifying WhatsApp protocols.
        - **Persistent:** Session files are stored locally on your machine in `b:\\Project\\AyuDevices\\wa_session`.
        - **Parallel Use:** You can continue using WhatsApp normally on your phone while the automation runs.
        """)

# ══════════════════ TAB 2: TEST SEND (TEXT & FILES/MEDIA) ═══════════════════
with tab_test:
    st.subheader("Test Message Delivery")
    st.markdown("Send test messages or attach **multiple files, photos, or videos** directly to any WhatsApp number.")

    test_type = st.radio(
        "Test Type:",
        ["💬 Text Message", "📁 Files / Photos / Videos (Multiple Supported)"],
        horizontal=True,
    )

    with st.form("wa_test_form"):
        test_mobile = st.text_input(
            "Recipient WhatsApp Number (with country code):",
            placeholder="+919876543210",
            help="Include country code, e.g. +91 for India, +1 for US."
        )

        test_text = st.text_area(
            "Message Content / Caption:",
            value="Hello from AyuSynk! Testing WhatsApp Web file delivery. 🩺✨",
            height=90,
        )

        uploaded_files = []
        if "Files" in test_type:
            uploaded_files = st.file_uploader(
                "Upload file(s) — select one or more PDFs, images, or videos:",
                type=["pdf", "png", "jpg", "jpeg", "mp4", "mov", "docx", "xlsx", "csv"],
                accept_multiple_files=True,
                help="You can drag & drop or select multiple files at once.",
            )
            if uploaded_files:
                st.caption(f"📎 **{len(uploaded_files)} file(s) selected:** {', '.join(f.name for f in uploaded_files)}")

        submit_test = st.form_submit_button("📲 Send Test via WhatsApp Web", use_container_width=True, type="primary")

        if submit_test:
            if not test_mobile or len(test_mobile.strip()) < 8:
                st.error("Please enter a valid phone number with country code (e.g. +919876543210).")
            else:
                with st.spinner("Automating browser to send message..."):
                    try:
                        if "Files" in test_type:
                            files_to_send = []
                            if uploaded_files:
                                temp_dir = ROOT / "storage" / "temp_uploads"
                                temp_dir.mkdir(parents=True, exist_ok=True)
                                for idx, f in enumerate(uploaded_files):
                                    tpath = temp_dir / f"{idx}_{f.name}"
                                    tpath.write_bytes(f.getbuffer())
                                    files_to_send.append(str(tpath))
                            else:
                                # Look for sample pitch deck
                                candidate = ROOT / "storage" / "AyuSynk_Pitch_Deck.pdf"
                                if candidate.exists():
                                    files_to_send.append(str(candidate))
                                else:
                                    pdf_list = list((ROOT / "storage").glob("*.pdf"))
                                    if pdf_list:
                                        files_to_send.append(str(pdf_list[0]))

                            if not files_to_send:
                                st.error("No files selected to send. Please upload one or more files in the uploader above.")
                            else:
                                res = send_whatsapp_message(
                                    mobile=test_mobile,
                                    files=files_to_send,
                                    caption=test_text,
                                )
                                sent_names = res.get("files", [Path(p).name for p in files_to_send])
                                st.success(f"✅ Successfully dispatched **{len(sent_names)} file(s)** to `{test_mobile}`!")
                                for fn in sent_names:
                                    st.write(f"- 📎 `{fn}`")
                        else:
                            res = send_whatsapp_message(mobile=test_mobile, text=test_text)
                            st.success(f"✅ Text message sent successfully to `{test_mobile}`!")

                    except Exception as e:
                        st.error(f"❌ Send failed: {e}")
                        st.info("Tip: Make sure WhatsApp Web is linked. If not, use the Setup Wizard in Tab 1.")

# ══════════════════ TAB 3: PIPELINE AUTO-SEND ═════════════════════════════════
with tab_auto:
    st.subheader("Automated Outreach Sending")
    st.markdown("""
    When messages are prepared through the **Pipeline Executions** page, the auto-sender will dispatch
    them one by one with safe randomized delays to mimic natural human behavior.
    """)

    from config.settings import settings
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("AUTO_SEND_ENABLED", str(getattr(settings, "AUTO_SEND_ENABLED", True)))
    with c2:
        st.metric("Pacing Delay (Seconds)", f"{getattr(settings, 'AUTO_SEND_DELAY_SECONDS', 5)}s")
    with c3:
        st.metric("Scheduler Timezone", str(getattr(settings, "SCHEDULER_TIMEZONE", "Asia/Kolkata")))

    st.markdown("---")
    st.markdown("#### ⚡ Trigger Immediate Outreach Dispatch")
    st.caption("Sends all currently prepared messages waiting in the pipeline queue.")

    if st.button("🚀 Send All Prepared Messages Now", type="primary", use_container_width=True):
        try:
            with st.spinner("Dispatching prepared outreach messages..."):
                result = api.post("/api/executions/auto-send-now")
                sent = result.get("sent", 0)
                failed = result.get("failed", 0)
                total = result.get("total_prepared", 0)
                if sent > 0:
                    st.success(f"✅ Outreach dispatch complete! Sent: **{sent}** | Failed: **{failed}** of {total} prepared.")
                else:
                    st.info(f"No pending prepared messages to send. (Prepared in queue: {total})")
        except Exception as e:
            st.error(f"Failed to dispatch: {e}")

# ══════════════════ TAB 4: SESSION & TROUBLESHOOTING ═════════════════════════
with tab_manage:
    st.subheader("WhatsApp Web Session & Process Controls")

    session_dir_display = session_info.get("session_dir") or "wa_session"
    browser_status_text = "Yes 🟢" if browser_open else "No ⚪"
    session_files_text = "Found ✅" if session_exists else "Not found ❌"

    st.markdown(f"""
    **Session Storage Path:**  
    `{session_dir_display}`
    
    **Current Status:**  
    - Browser Active: `{browser_status_text}`
    - Saved Profile Files: `{session_files_text}`
    """)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🚪 Close Background Browser Window", use_container_width=True):
            wa_web_close()
            st.success("Browser closed cleanly. Next send will launch a fresh window.")

    with col_btn2:
        if st.button("🔄 Unlink & Wipe Session (Switch Phone)", use_container_width=True):
            res = wa_web_reset_session()
            if res.get("status") == "success":
                st.warning("⚠️ Session wiped. Return to Tab 1 to scan QR code with your new phone.")
            else:
                st.error(f"Error resetting: {res.get('message')}")

    st.divider()
    st.markdown("#### ❓ Frequently Asked Questions & Troubleshooting")
    with st.expander("Do I need to keep the browser window open?"):
        st.markdown("The Playwright browser manages its own lifecycle. You can minimize the window, but do not close it while a batch send is in progress.")

    with st.expander("Does WhatsApp Web log out after some time?"):
        st.markdown("WhatsApp Web sessions usually remain active for 14 to 30 days unless you manually disconnect the device from your phone or clear browser cookies.")

    with st.expander("How do I avoid WhatsApp spam flags?"):
        st.markdown("""
        - Always keep `AUTO_SEND_DELAY_SECONDS` between 5 and 15 seconds.
        - Send personalized templates using doctor names and specialties.
        - Do not blast thousands of messages in a single hour from a new WhatsApp account.
        """)
