"""
Auto-Send Engine.

When AUTO_SEND_ENABLED=true and a WhatsApp API is configured, this engine:
  1. Finds all prepared (ready-to-send) executions.
  2. Sends each one automatically via the configured API.
  3. Marks them as sent and advances the pipeline.
  4. Adds a configurable delay between sends to avoid rate limits.

Called by the APScheduler every 15 minutes (same job as the poller).
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.database.models import PipelineExecution, ExecutionStatus
from app.core.pipeline_engine import mark_step_sent, mark_step_failed
from app.core.whatsapp import (
    send_whatsapp_message,
    is_auto_send_enabled, get_active_mode,
)
from config.settings import settings

logger = logging.getLogger(__name__)


def auto_send_prepared(db: Session) -> dict:
    """
    Send all prepared executions automatically.
    Returns a summary dict with counts.
    """
    if not is_auto_send_enabled():
        return {"skipped": "auto-send not enabled or no API configured"}

    prepared: list[PipelineExecution] = (
        db.query(PipelineExecution)
        .filter_by(status=ExecutionStatus.prepared)
        .all()
    )

    mode = get_active_mode()
    sent_count = 0
    failed_count = 0
    skipped_count = 0

    logger.info(
        "[AutoSend] Mode=%s | %d message(s) to send", mode, len(prepared)
    )

    for ex in prepared:
        enrollment = ex.enrollment
        doctor = enrollment.doctor

        # Skip opted-out doctors
        if doctor.opted_out:
            logger.info("[AutoSend] Skipping opted-out doctor: %s", doctor.name)
            ex.status = ExecutionStatus.skipped
            ex.error_message = "Doctor opted out"
            db.commit()
            skipped_count += 1
            continue

        mobile = doctor.mobile
        message = ex.rendered_message
        media_path = ex.media_path

        try:
            wa_msg_id = None
            step = ex.step
            caption = f"AyuSynk 2+ — {step.name}" if (media_path and not message) else None

            # Single centralized WhatsApp send call handling text and/or media
            result = send_whatsapp_message(
                mobile=mobile,
                text=message if message else None,
                files=media_path if media_path else None,
                caption=caption,
                recipient_name=doctor.name,
            )
            wa_msg_id = _extract_message_id(result)
            logger.info(
                "[AutoSend] ✅ Message sent to %s (%s) | id=%s",
                doctor.name, mobile, wa_msg_id,
            )

            mark_step_sent(db, ex, wa_msg_id)
            db.commit()
            sent_count += 1

        except Exception as exc:
            db.rollback()
            error_str = str(exc)
            logger.error(
                "[AutoSend] ❌ Failed for %s (%s): %s",
                doctor.name, mobile, error_str,
            )
            try:
                mark_step_failed(db, ex, error_str)
                db.commit()
            except Exception:
                db.rollback()
            failed_count += 1

        # Rate-limit delay between sends
        if settings.AUTO_SEND_DELAY_SECONDS > 0:
            time.sleep(settings.AUTO_SEND_DELAY_SECONDS)

    summary = {
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total_prepared": len(prepared),
    }
    logger.info("[AutoSend] Done: %s", summary)
    return summary


def _extract_message_id(result: dict) -> str | None:
    """Extract message ID from Green API or Meta API response."""
    # Green API: {"idMessage": "..."}
    if "idMessage" in result:
        return result["idMessage"]
    # Meta API: {"messages": [{"id": "..."}]}
    messages = result.get("messages", [])
    if messages:
        return messages[0].get("id")
    return None
