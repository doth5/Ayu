"""
WhatsApp integration layer.

Delivery modes (auto-detected from .env settings):

  1. WA WEB AUTOMATION (Playwright — no external API needed)  [PRIMARY]
     - Set WA_WEB_ENABLED=true in .env
     - First run: browser opens, scan QR once
     - Subsequent runs: session is reused automatically
     - Sends text and files via real WhatsApp Web browser

  2. META BUSINESS API (official, scalable)  [OPTIONAL]
     - Set WHATSAPP_API_URL, WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID
     - Requires Meta business verification

  3. MANUAL-SEND (default fallback)
     - Generates wa.me link with message pre-filled
     - User clicks and presses Send manually

Priority: WA Web > Meta API > Manual
"""
from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Mode detection
# ─────────────────────────────────────────────────────────────────────────────

def _meta_api_configured() -> bool:
    return bool(
        settings.WHATSAPP_API_URL
        and settings.WHATSAPP_TOKEN
        and settings.WHATSAPP_PHONE_NUMBER_ID
    )


def _wa_web_configured() -> bool:
    """True if WhatsApp Web Playwright automation is enabled."""
    return bool(getattr(settings, "WA_WEB_ENABLED", False))


def get_active_mode() -> str:
    """Return the active delivery mode string."""
    if _wa_web_configured():
        return "wa_web"
    if _meta_api_configured():
        return "meta_api"
    return "manual"


def is_api_mode() -> bool:
    """True if any automated API mode is active."""
    return _wa_web_configured() or _meta_api_configured()


def is_auto_send_enabled() -> bool:
    """True if automated sending is both configured and enabled."""
    return is_api_mode() and settings.AUTO_SEND_ENABLED


# ─────────────────────────────────────────────────────────────────────────────
# Manual-send helper
# ─────────────────────────────────────────────────────────────────────────────

def build_wa_link(mobile: str, message: str) -> str:
    """Return a wa.me deep-link that opens WhatsApp with the message pre-filled."""
    clean = mobile.strip().replace(" ", "").replace("-", "").replace("+", "")
    return f"https://wa.me/{clean}?text={urllib.parse.quote(message)}"


def _clean_mobile(mobile: str) -> str:
    """Strip everything except digits."""
    return mobile.strip().replace("+", "").replace(" ", "").replace("-", "")


# ─────────────────────────────────────────────────────────────────────────────
# META BUSINESS API (optional)
# ─────────────────────────────────────────────────────────────────────────────






# ─────────────────────────────────────────────────────────────────────────────
# ── META BUSINESS API ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def meta_send_text(mobile: str, message: str) -> dict:
    url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": _clean_mobile(mobile),
        "type": "text",
        "text": {"body": message},
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def meta_send_media(
    mobile: str,
    media_type: str,
    media_url: str,
    caption: Optional[str] = None,
) -> dict:
    url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    media_payload: dict = {"link": media_url}
    if caption:
        media_payload["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": _clean_mobile(mobile),
        "type": media_type,
        media_type: media_payload,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# ── Unified Centralized Public API (used project-wide) ───────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def send_whatsapp_message(
    mobile: str,
    text: Optional[str] = None,
    files: Optional[list[str | Path] | str | Path] = None,
    caption: Optional[str] = None,
    recipient_name: Optional[str] = None,
    media_type: Optional[str] = None,
) -> dict:
    """
    Single centralized WhatsApp messaging entrypoint for the entire project.
    Used by:
      - Bulk messaging campaigns (app/api/routers/campaigns.py)
      - Pipelines & automated outreach (app/core/auto_sender.py)
      - Scheduled messages
      - Individual messages & test sends (app/api/routers/executions.py, Streamlit)

    Handles text and/or file attachments (images, PDFs, videos, DOCX) in a single unified call.
    Dynamically routes to the active WhatsApp delivery mode (wa_web, meta_api, or manual).
    """
    mode = get_active_mode()
    logger.info(
        "[WhatsApp] Central dispatch: mode=%s, mobile=%s, has_text=%s, has_files=%s",
        mode, mobile, bool(text), bool(files),
    )

    if mode == "wa_web":
        from app.core.whatsapp_web import wa_web_send_message
        return wa_web_send_message(
            mobile=mobile,
            text=text,
            files=files,
            caption=caption,
            recipient_name=recipient_name,
        )

    elif mode == "meta_api":
        res = {}
        if text:
            res = meta_send_text(mobile, text)
        if files:
            m_type = media_type or "document"
            if isinstance(files, (list, tuple)):
                for f in files:
                    res = meta_send_media(mobile, m_type, str(f), caption)
            else:
                res = meta_send_media(mobile, m_type, str(files), caption)
        return res

    elif mode == "manual":
        msg = (text or "") + (f"\n[Attachment: {caption or 'file'}]" if files else "")
        link = build_wa_link(mobile, msg)
        return {"status": "manual", "link": link, "mobile": mobile}

    else:
        raise RuntimeError(
            "No WhatsApp API configured. Set WA_WEB_ENABLED=true in .env to use "
            "WhatsApp Web automation, or configure Meta API credentials."
        )


def send_text_message(mobile: str, message: str, recipient_name: Optional[str] = None) -> dict:
    """Send text message via centralized send_whatsapp_message."""
    return send_whatsapp_message(mobile=mobile, text=message, recipient_name=recipient_name)


def send_media_message(
    mobile: str,
    media_type: str,
    file_path_or_url: str | list[str],
    caption: Optional[str] = None,
    recipient_name: Optional[str] = None,
) -> dict:
    """Send media message via centralized send_whatsapp_message."""
    return send_whatsapp_message(
        mobile=mobile,
        files=file_path_or_url,
        caption=caption,
        recipient_name=recipient_name,
        media_type=media_type,
    )


def send_files_message(
    mobile: str,
    file_paths: list[str] | str,
    caption: Optional[str] = None,
    recipient_name: Optional[str] = None,
) -> dict:
    """Send one or multiple files via centralized send_whatsapp_message."""
    return send_whatsapp_message(
        mobile=mobile,
        files=file_paths,
        caption=caption,
        recipient_name=recipient_name,
    )
