"""Executions API – prepare, mark sent, mark failed, get prepared messages."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import (
    DoctorPipelineEnrollment, PipelineExecution, ExecutionStatus,
    Doctor, DoctorStatus,
)
from app.core.pipeline_engine import (
    get_next_pending_step, prepare_step, mark_step_sent,
    mark_step_failed, check_conditions,
)
from app.core.whatsapp import build_wa_link, is_api_mode

router = APIRouter()


class ExecutionOut(BaseModel):
    id: int
    enrollment_id: int
    step_id: int
    status: str
    rendered_message: Optional[str]
    media_path: Optional[str]
    whatsapp_message_id: Optional[str]
    prepared_at: Optional[datetime]
    sent_at: Optional[datetime]
    model_config = {"from_attributes": True}


class PreparedMessage(BaseModel):
    execution_id: int
    doctor_id: int
    doctor_name: str
    mobile: str
    message: Optional[str]
    media_path: Optional[str]
    step_name: str
    wa_link: Optional[str]
    api_mode: bool


@router.get("/prepared", response_model=list[PreparedMessage])
def get_prepared_messages(db: Session = Depends(get_db)):
    """
    Return all executions that are prepared but not yet sent.
    These are the messages the user needs to send today.
    """
    execs = (
        db.query(PipelineExecution)
        .filter_by(status=ExecutionStatus.prepared)
        .all()
    )
    results = []
    for ex in execs:
        enrollment = ex.enrollment
        doctor = enrollment.doctor
        if doctor.opted_out:
            continue
        wa_link = None
        if ex.rendered_message:
            wa_link = build_wa_link(doctor.mobile, ex.rendered_message)
        results.append(
            PreparedMessage(
                execution_id=ex.id,
                doctor_id=doctor.id,
                doctor_name=doctor.name,
                mobile=doctor.mobile,
                message=ex.rendered_message,
                media_path=ex.media_path,
                step_name=ex.step.name,
                wa_link=wa_link,
                api_mode=is_api_mode(),
            )
        )
    return results


@router.post("/{execution_id}/mark-sent", response_model=ExecutionOut)
def mark_execution_sent(
    execution_id: int,
    whatsapp_message_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    ex = db.get(PipelineExecution, execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    if ex.status == ExecutionStatus.sent:
        raise HTTPException(400, "Already marked as sent")
    mark_step_sent(db, ex, whatsapp_message_id)
    db.commit()
    db.refresh(ex)
    return ex


@router.post("/{execution_id}/mark-failed", response_model=ExecutionOut)
def mark_execution_failed(execution_id: int, error: str = "", db: Session = Depends(get_db)):
    ex = db.get(PipelineExecution, execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    mark_step_failed(db, ex, error)
    db.commit()
    db.refresh(ex)
    return ex


@router.post("/prepare-due")
def prepare_due_executions(db: Session = Depends(get_db)):
    """Manually trigger preparation of all due pipeline steps."""
    from app.core.pipeline_engine import get_due_enrollments
    due = get_due_enrollments(db)
    prepared = 0
    for enrollment in due:
        step = get_next_pending_step(db, enrollment)
        if step and check_conditions(step, enrollment):
            prepare_step(db, enrollment, step)
            prepared += 1
    db.commit()
    return {"prepared": prepared}


@router.get("/history/{doctor_id}", response_model=list[ExecutionOut])
def doctor_execution_history(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(404, "Doctor not found")
    execs = []
    for enrollment in doctor.enrollments:
        execs.extend(enrollment.executions)
    execs.sort(key=lambda e: e.created_at, reverse=True)
    return execs


@router.post("/auto-send-now")
def trigger_auto_send(db: Session = Depends(get_db)):
    """
    Manually trigger an immediate auto-send of all prepared messages.
    Works regardless of the scheduler interval.
    """
    from app.core.auto_sender import auto_send_prepared
    from app.core.whatsapp import is_api_mode, get_active_mode
    from config.settings import settings

    if not is_api_mode():
        raise HTTPException(
            400,
            "No WhatsApp API configured. Add GREEN_API_INSTANCE_ID + GREEN_API_TOKEN to .env",
        )
    if not settings.AUTO_SEND_ENABLED:
        raise HTTPException(
            400,
            "AUTO_SEND_ENABLED is false. Set AUTO_SEND_ENABLED=true in .env to enable.",
        )
    summary = auto_send_prepared(db)
    return summary


@router.get("/whatsapp-status")
def whatsapp_status():
    """Check current WhatsApp connection and delivery mode."""
    from app.core.whatsapp import (
        get_active_mode, is_auto_send_enabled,
        _meta_api_configured, _wa_web_configured,
    )
    from config.settings import settings

    mode = get_active_mode()
    return {
        "mode": mode,
        "auto_send_enabled": settings.AUTO_SEND_ENABLED,
        "auto_send_active": is_auto_send_enabled(),
        "wa_web_enabled": _wa_web_configured(),
        "wa_web_session_dir": str(getattr(settings, "WA_WEB_SESSION_DIR", "wa_session")),
        "meta_api_configured": _meta_api_configured(),
        # Legacy fields — kept empty for backward compat with older UI code
        "instances": [],
        "instance_count": 0,
        "green_api_configured": False,
    }




@router.get("/whatsapp-web-status")
def whatsapp_web_status():
    """Get WhatsApp Web automation session and login status."""
    try:
        from app.core.whatsapp_web import wa_web_get_session_status
        return wa_web_get_session_status()
    except Exception as e:
        raise HTTPException(500, f"Error getting session status: {e}")


@router.post("/whatsapp-web-setup")
def whatsapp_web_setup(timeout_seconds: int = 180):
    """Launch WhatsApp Web browser for first-time QR scan or session verification."""
    try:
        from app.core.whatsapp_web import wa_web_open_for_setup
        return wa_web_open_for_setup(qr_timeout_seconds=timeout_seconds)
    except Exception as e:
        raise HTTPException(500, f"Error launching setup: {e}")







class TestSendRequest(BaseModel):
    mobile: str
    message: str


@router.post("/test-send")
def test_send(body: TestSendRequest):
    """Send a test WhatsApp message using current delivery mode (WA Web / Meta API / Manual)."""
    from app.core.whatsapp import send_whatsapp_message
    try:
        result = send_whatsapp_message(body.mobile, text=body.message)
        return {
            "status": "success",
            "mode": result.get("mode", "unknown"),
            "raw": result,
        }
    except Exception as e:
        raise HTTPException(400, f"Test send failed: {e}")
