"""
Bulk Campaigns API Router.

Provides endpoints to:
  - Create / list / get / delete campaigns
  - Start / pause / resume / cancel a campaign
  - Poll live progress via GET /{id}

The campaign sender runs in a background daemon thread:
  - Sends one doctor at a time
  - Waits a random delay_min..delay_max seconds between sends
  - Persists per-recipient status after every send
  - Respects pause / cancel signals from the database
  - Skips opted-out doctors
  - Supports campaign resume (skips already-sent recipients)
"""
from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import SessionLocal, get_db
from app.database.models import (
    BulkCampaign, BulkCampaignRecipient,
    CampaignStatus, RecipientStatus, Doctor,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Thread-safe active campaign set; prevents duplicate runner threads
_active_campaign_ids: set[int] = set()
_active_lock = threading.Lock()


# -- Pydantic schemas ----------------------------------------------------------

class CampaignCreate(BaseModel):
    name: str
    message_type: str = "text"
    text_message: Optional[str] = None
    caption: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    delay_min: int = 10
    delay_max: int = 20
    doctor_ids: list[int] = []


class RecipientOut(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    mobile: str
    status: str
    error_message: Optional[str]
    sent_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CampaignOut(BaseModel):
    id: int
    name: str
    message_type: str
    text_message: Optional[str]
    caption: Optional[str]
    file_path: Optional[str]
    file_name: Optional[str]
    delay_min: int
    delay_max: int
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    skipped_count: int
    current_recipient_index: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime
    recipients: list[RecipientOut] = []

    model_config = {"from_attributes": True}


# -- Background sender ---------------------------------------------------------

def _run_campaign(campaign_id: int):
    """
    Background worker: sequentially sends messages to all pending recipients.
    """
    logger.info("[Campaign %d] Worker thread started.", campaign_id)
    db: Session = SessionLocal()
    try:
        campaign = db.get(BulkCampaign, campaign_id)
        if not campaign:
            logger.error("[Campaign %d] Not found. Aborting.", campaign_id)
            return

        campaign.status = CampaignStatus.running
        campaign.started_at = campaign.started_at or datetime.utcnow()
        db.commit()

        from app.core.whatsapp import send_whatsapp_message, get_active_mode

        # Ensure WhatsApp Web Chromium browser is open and ready before sending
        if get_active_mode() == "wa_web":
            try:
                from app.core.whatsapp_web import wa_web_open_for_setup
                logger.info("[Campaign %d] Ensuring WhatsApp Chromium browser is open and ready...", campaign_id)
                wa_web_open_for_setup(qr_timeout_seconds=120)
            except Exception as e:
                logger.warning("[Campaign %d] Pre-launch WhatsApp browser check warning: %s", campaign_id, e)

        for idx, recipient in enumerate(campaign.recipients):
            # Re-read campaign status for pause/cancel signals
            db.refresh(campaign)
            if campaign.status == CampaignStatus.cancelled:
                logger.info("[Campaign %d] Cancelled - stopping.", campaign_id)
                break

            while campaign.status == CampaignStatus.paused:
                logger.info("[Campaign %d] Paused - waiting...", campaign_id)
                time.sleep(2)
                db.refresh(campaign)
                if campaign.status == CampaignStatus.cancelled:
                    break

            if campaign.status == CampaignStatus.cancelled:
                break

            # Skip already completed recipients
            if recipient.status in (RecipientStatus.sent, RecipientStatus.skipped):
                continue

            # Skip opted-out doctors
            doctor = db.get(Doctor, recipient.doctor_id)
            if not doctor or doctor.opted_out:
                recipient.status = RecipientStatus.skipped
                recipient.error_message = "Doctor opted out or not found"
                campaign.skipped_count += 1
                campaign.current_recipient_index = idx + 1
                db.commit()
                continue

            recipient.status = RecipientStatus.sending
            campaign.current_recipient_index = idx
            db.commit()

            logger.info(
                "[Campaign %d] Sending to %s (%s) [%d/%d]...",
                campaign_id, recipient.doctor_name, recipient.mobile,
                idx + 1, campaign.total_recipients,
            )

            try:
                # Single centralized WhatsApp send call handling text, files, and captions
                send_whatsapp_message(
                    mobile=recipient.mobile,
                    text=campaign.text_message if campaign.text_message else None,
                    files=campaign.file_path if campaign.file_path else None,
                    caption=campaign.caption,
                    recipient_name=recipient.doctor_name,
                )

                recipient.status = RecipientStatus.sent
                recipient.sent_at = datetime.utcnow()
                recipient.error_message = None
                campaign.sent_count += 1
                logger.info("[Campaign %d] Sent to %s.", campaign_id, recipient.mobile)

            except Exception as exc:
                logger.error("[Campaign %d] Failed %s: %s", campaign_id, recipient.mobile, exc)
                recipient.status = RecipientStatus.failed
                recipient.error_message = str(exc)[:500]
                campaign.failed_count += 1

            campaign.current_recipient_index = idx + 1
            db.commit()

            # Delay before next recipient
            remaining = [
                r for r in campaign.recipients[idx + 1:]
                if r.status not in (RecipientStatus.sent, RecipientStatus.skipped)
            ]
            if remaining:
                db.refresh(campaign)
                if campaign.status not in (CampaignStatus.cancelled, CampaignStatus.paused):
                    delay = random.randint(campaign.delay_min, campaign.delay_max)
                    logger.info("[Campaign %d] Waiting %ds before next send...", campaign_id, delay)
                    time.sleep(delay)

        db.refresh(campaign)
        if campaign.status != CampaignStatus.cancelled:
            campaign.status = CampaignStatus.completed
            campaign.completed_at = datetime.utcnow()
        db.commit()
        logger.info("[Campaign %d] Finished. Status=%s", campaign_id, campaign.status)

    except Exception as exc:
        logger.exception("[Campaign %d] Worker error: %s", campaign_id, exc)
        try:
            db.refresh(campaign)
            campaign.status = CampaignStatus.paused
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
        with _active_lock:
            _active_campaign_ids.discard(campaign_id)


# -- Endpoints -----------------------------------------------------------------

@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    """Create a new bulk campaign draft with selected recipients."""
    if not payload.name.strip():
        raise HTTPException(400, "Campaign name cannot be empty.")
    if payload.delay_min < 1 or payload.delay_max < payload.delay_min:
        raise HTTPException(400, "delay_min must be >=1 and <=delay_max.")

    campaign = BulkCampaign(
        name=payload.name.strip(),
        message_type=payload.message_type,
        text_message=payload.text_message,
        caption=payload.caption,
        file_path=payload.file_path,
        file_name=payload.file_name,
        delay_min=payload.delay_min,
        delay_max=payload.delay_max,
        status=CampaignStatus.draft,
    )
    db.add(campaign)
    db.flush()

    recipients_added = 0
    for doc_id in payload.doctor_ids:
        doctor = db.get(Doctor, doc_id)
        if not doctor:
            continue
        if doctor.opted_out:
            r = BulkCampaignRecipient(
                campaign_id=campaign.id,
                doctor_id=doctor.id,
                doctor_name=doctor.name,
                mobile=doctor.mobile,
                status=RecipientStatus.skipped,
                error_message="Doctor opted out at campaign creation",
            )
        else:
            r = BulkCampaignRecipient(
                campaign_id=campaign.id,
                doctor_id=doctor.id,
                doctor_name=doctor.name,
                mobile=doctor.mobile,
                status=RecipientStatus.pending,
            )
            recipients_added += 1
        db.add(r)

    campaign.total_recipients = len(payload.doctor_ids)
    campaign.skipped_count = campaign.total_recipients - recipients_added
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(BulkCampaign).order_by(BulkCampaign.created_at.desc()).all()


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.get(BulkCampaign, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found.")
    return c


@router.post("/{campaign_id}/start")
def start_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Start or resume a campaign in a background thread."""
    c = db.get(BulkCampaign, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found.")
    if c.status == CampaignStatus.running:
        raise HTTPException(400, "Campaign is already running.")
    if c.status == CampaignStatus.completed:
        raise HTTPException(400, "Campaign already completed.")
    if c.status == CampaignStatus.cancelled:
        raise HTTPException(400, "Campaign is cancelled. Create a new one to retry.")

    with _active_lock:
        if campaign_id in _active_campaign_ids:
            raise HTTPException(400, "Campaign worker is already active.")
        _active_campaign_ids.add(campaign_id)

    c.status = CampaignStatus.running
    c.started_at = c.started_at or datetime.utcnow()
    db.commit()

    t = threading.Thread(
        target=_run_campaign,
        args=(campaign_id,),
        daemon=True,
        name=f"campaign-{campaign_id}",
    )
    t.start()
    return {"status": "started", "campaign_id": campaign_id}


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.get(BulkCampaign, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found.")
    if c.status != CampaignStatus.running:
        raise HTTPException(400, f"Campaign not running (status={c.status}).")
    c.status = CampaignStatus.paused
    db.commit()
    return {"status": "paused", "campaign_id": campaign_id}


@router.post("/{campaign_id}/resume")
def resume_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.get(BulkCampaign, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found.")
    if c.status not in (CampaignStatus.paused, CampaignStatus.draft):
        raise HTTPException(400, f"Cannot resume campaign (status={c.status}).")
    return start_campaign(campaign_id, db)


@router.post("/{campaign_id}/cancel")
def cancel_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.get(BulkCampaign, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found.")
    c.status = CampaignStatus.cancelled
    c.completed_at = datetime.utcnow()
    for r in c.recipients:
        if r.status in (RecipientStatus.pending, RecipientStatus.sending):
            r.status = RecipientStatus.skipped
            r.error_message = "Campaign cancelled"
            c.skipped_count += 1
    db.commit()
    return {"status": "cancelled", "campaign_id": campaign_id}


@router.delete("/{campaign_id}", status_code=200)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.get(BulkCampaign, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found.")
    if c.status == CampaignStatus.running:
        raise HTTPException(400, "Cannot delete a running campaign. Pause or cancel it first.")
    db.delete(c)
    db.commit()
    return {"status": "deleted", "campaign_id": campaign_id}
