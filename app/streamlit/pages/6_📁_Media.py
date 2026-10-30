"""Media library page – upload and manage videos, images, PDFs, documents."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import requests
from app.streamlit.utils import api_client as api
from config.settings import settings

st.set_page_config(page_title="Media – AyuSynk", page_icon="📁", layout="wide")

SPECIALTIES = [
    "General Physician", "Pediatrician", "Cardiologist", "Pulmonologist",
    "Surgeon", "Anesthesiologist", "Orthopedic", "Emergency Medicine",
    "Gynecologist", "Medical Student", "Professor",
]
MEDIA_TYPES = ["image", "video", "pdf", "document", "audio"]

st.markdown("""
<div class="page-header">
  <h1>📁 Media Library</h1>
  <p>Upload and manage videos, images, PDFs, brochures, and documents for pipeline steps.</p>
</div>
""", unsafe_allow_html=True)

tab_library, tab_upload = st.tabs(["📚 Library", "⬆️ Upload"])

# ── Library ───────────────────────────────────────────────────────────────────
with tab_library:
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        filter_type = st.selectbox("Filter by Type", ["All"] + MEDIA_TYPES)
    with fcol2:
        filter_spec = st.selectbox("Filter by Specialty", ["All (including universal)"] + SPECIALTIES)

    params = {}
    if filter_type != "All":
        params["media_type"] = filter_type
    if filter_spec != "All (including universal)":
        params["specialty"] = filter_spec

    try:
        media_list = api.get("/api/media", **params)
    except Exception as e:
        st.error(f"Could not load media: {e}")
        media_list = []

    if not media_list:
        st.info("No media files found. Upload some using the 'Upload' tab.")
    else:
        st.caption(f"{len(media_list)} file(s)")

        # Display in a grid
        cols_per_row = 3
        for i in range(0, len(media_list), cols_per_row):
            row = media_list[i:i + cols_per_row]
            grid_cols = st.columns(cols_per_row)
            for col, item in zip(grid_cols, row):
                with col:
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background:#1e2d45;border:1px solid #2d4a6e;
                                        border-radius:12px;padding:16px;margin-bottom:8px;">
                              <div style="font-weight:600;color:#60a5fa;margin-bottom:4px;">
                                {item['name']}
                              </div>
                              <div style="color:#94a3b8;font-size:0.8rem;">
                                Type: {item['media_type']} |
                                ID: {item['id']}
                              </div>
                              <div style="color:#64748b;font-size:0.75rem;margin-top:2px;">
                                {item.get('specialty') or 'Universal'}
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # Preview image
                        file_path = item.get("file_path", "")
                        if file_path:
                            p = Path(file_path)
                            if p.exists() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                                st.image(str(p), use_container_width=True)

                        if item.get("description"):
                            st.caption(item["description"])

                        size_kb = (item.get("file_size_bytes") or 0) // 1024
                        st.caption(f"Size: {size_kb} KB | MIME: {item.get('mime_type', 'unknown')}")

                        if st.button("🗑️ Delete", key=f"del_media_{item['id']}"):
                            try:
                                api.delete(f"/api/media/{item['id']}")
                                st.success("Deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

# ── Upload ────────────────────────────────────────────────────────────────────
with tab_upload:
    st.subheader("Upload New Media File")
    with st.form("upload_form", clear_on_submit=True):
        uc1, uc2 = st.columns(2)
        with uc1:
            u_name = st.text_input("Display Name *", placeholder="AyuSynk 2+ Demo Video")
            u_type = st.selectbox("Media Type *", MEDIA_TYPES)
            u_specialty = st.selectbox("Specialty (optional)", ["Universal"] + SPECIALTIES)
        with uc2:
            u_desc = st.text_area("Description", placeholder="Short description of this file…", height=100)
            u_file = st.file_uploader(
                f"Upload file * (max {settings.MAX_UPLOAD_MB} MB)",
                type=["jpg", "jpeg", "png", "webp", "gif", "mp4", "mpeg", "mov",
                      "pdf", "doc", "docx", "mp3", "wav", "ogg"],
            )

        upload_submitted = st.form_submit_button("⬆️ Upload File", use_container_width=True)
        if upload_submitted:
            if not u_name or not u_file:
                st.error("Name and file are required.")
            else:
                try:
                    files = {"file": (u_file.name, u_file.getvalue(), u_file.type)}
                    data = {
                        "name": u_name,
                        "media_type": u_type,
                        "specialty": None if u_specialty == "Universal" else u_specialty,
                        "description": u_desc or None,
                    }
                    r = requests.post(
                        f"{settings.API_BASE_URL}/api/media",
                        data={k: v for k, v in data.items() if v is not None},
                        files=files,
                        timeout=60,
                    )
                    r.raise_for_status()
                    result = r.json()
                    st.success(f"✅ **{result['name']}** uploaded successfully! (ID: {result['id']})")
                except Exception as e:
                    st.error(f"Upload failed: {e}")
