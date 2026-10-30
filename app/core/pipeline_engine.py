"""
Pipeline Execution Engine.

Responsibilities:
- Enrol a doctor in the correct pipeline when they are added.
- Determine which step is next (respecting delays and conditions).
- Prepare (render) the message for a step.
- Mark steps as sent/failed.
- Advance the pipeline after a step is sent.
- Prevent duplicates via idempotency checks.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
from sqlalchemy.orm import Session

from app.database.models import (
    Doctor, DoctorPipelineEnrollment, ExecutionStatus, MessageLog,
    Pipeline, PipelineExecution, PipelineStep, DoctorStatus,
)
from app.core.template_engine import build_doctor_context, render_template
from config.settings import settings

logger = logging.getLogger(__name__)
TZ = pytz.timezone(settings.SCHEDULER_TIMEZONE)


# ── Enrolment ─────────────────────────────────────────────────────────────────

def enrol_doctor(db: Session, doctor: Doctor) -> Optional[DoctorPipelineEnrollment]:
    """
    Find the pipeline matching the doctor's specialty and enrol them.
    Idempotent – does nothing if doctor already has an active enrollment or is opted out.
    """
    if doctor.opted_out:
        logger.info("Doctor %s is opted out, skipping pipeline enrollment.", doctor.name)
        return None

    existing = (
        db.query(DoctorPipelineEnrollment)
        .filter_by(doctor_id=doctor.id, status=DoctorStatus.active)
        .first()
    )
    if existing:
        return existing

    pipeline = db.query(Pipeline).filter_by(specialty=doctor.specialty, is_active=True).first()
    if not pipeline:
        logger.warning("No active pipeline found for specialty: %s", doctor.specialty)
        return None

    first_step = (
        db.query(PipelineStep)
        .filter_by(pipeline_id=pipeline.id, is_active=True)
        .order_by(PipelineStep.step_order)
        .first()
    )

    enrollment = DoctorPipelineEnrollment(
        doctor_id=doctor.id,
        pipeline_id=pipeline.id,
        current_step_order=first_step.step_order if first_step else 1,
        status=DoctorStatus.active,
        next_action_at=datetime.now(TZ).replace(tzinfo=None),  # ready immediately
    )
    db.add(enrollment)
    db.flush()
    logger.info("Enrolled doctor %s in pipeline '%s'", doctor.name, pipeline.name)
    return enrollment


# ── Next eligible step ────────────────────────────────────────────────────────

def get_next_pending_step(
    db: Session, enrollment: DoctorPipelineEnrollment
) -> Optional[PipelineStep]:
    """Return the next active pipeline step that has not been sent yet."""
    sent_step_ids = {
        ex.step_id
        for ex in enrollment.executions
        if ex.status == ExecutionStatus.sent
    }

    steps = (
        db.query(PipelineStep)
        .filter_by(pipeline_id=enrollment.pipeline_id, is_active=True)
        .order_by(PipelineStep.step_order)
        .all()
    )

    for step in steps:
        if step.id not in sent_step_ids:
            return step
    return None  # pipeline complete


def check_conditions(step: PipelineStep, enrollment: DoctorPipelineEnrollment) -> bool:
    """Evaluate any step conditions. Returns True if safe to proceed."""
    if not step.conditions:
        return True
    try:
        conds = json.loads(step.conditions)
    except json.JSONDecodeError:
        return True

    # Condition: require no prior reply from doctor
    if conds.get("require_no_reply"):
        replied = any(
            ex.status == ExecutionStatus.replied for ex in enrollment.executions
        )
        if replied:
            return False
    return True


# ── Prepare step (render message) ─────────────────────────────────────────────

def prepare_step(
    db: Session,
    enrollment: DoctorPipelineEnrollment,
    step: PipelineStep,
) -> Optional[PipelineExecution]:
    """
    Render the message template for a step and create an execution record.
    Idempotent – returns existing execution if already prepared.
    Never prepares messages for opted-out doctors.
    """
    doctor = enrollment.doctor
    if doctor.opted_out:
        logger.info("Doctor %s is opted out, skipping message preparation.", doctor.name)
        return None

    existing = (
        db.query(PipelineExecution)
        .filter_by(enrollment_id=enrollment.id, step_id=step.id)
        .filter(PipelineExecution.status.in_([ExecutionStatus.prepared, ExecutionStatus.sent]))
        .first()
    )
    if existing:
        return existing

    context = build_doctor_context(doctor)

    rendered = None
    if step.template:
        rendered = render_template(step.template.content, context)

    media_path = step.media_file.file_path if step.media_file else None

    execution = PipelineExecution(
        enrollment_id=enrollment.id,
        step_id=step.id,
        status=ExecutionStatus.prepared,
        rendered_message=rendered,
        media_path=media_path,
        prepared_at=datetime.utcnow(),
    )
    db.add(execution)
    db.flush()
    return execution


# ── Mark step as sent ─────────────────────────────────────────────────────────

def mark_step_sent(
    db: Session,
    execution: PipelineExecution,
    whatsapp_message_id: Optional[str] = None,
):
    """Record that a step was successfully sent and advance the enrollment."""
    execution.status = ExecutionStatus.sent
    execution.whatsapp_message_id = whatsapp_message_id
    execution.sent_at = datetime.utcnow()

    enrollment = execution.enrollment
    step = execution.step

    # Log the message
    log = MessageLog(
        doctor_id=enrollment.doctor_id,
        execution_id=execution.id,
        direction="outbound",
        message_content=execution.rendered_message,
        media_path=execution.media_path,
        status="sent",
        whatsapp_message_id=whatsapp_message_id,
        sent_at=datetime.utcnow(),
    )
    db.add(log)

    # Advance enrollment to next step
    _advance_enrollment(db, enrollment, step)
    db.flush()


def mark_step_failed(db: Session, execution: PipelineExecution, error: str):
    execution.status = ExecutionStatus.failed
    execution.error_message = error
    db.flush()


def _advance_enrollment(
    db: Session,
    enrollment: DoctorPipelineEnrollment,
    sent_step: PipelineStep,
):
    """Move the enrollment pointer and calculate next_action_at."""
    next_step = (
        db.query(PipelineStep)
        .filter(
            PipelineStep.pipeline_id == enrollment.pipeline_id,
            PipelineStep.is_active == True,
            PipelineStep.step_order > sent_step.step_order,
        )
        .order_by(PipelineStep.step_order)
        .first()
    )

    if next_step:
        enrollment.current_step_order = next_step.step_order
        delay_hours = next_step.delay_hours or 0.0
        enrollment.next_action_at = datetime.utcnow() + timedelta(hours=delay_hours)
    else:
        # Pipeline complete
        enrollment.status = DoctorStatus.completed
        enrollment.completed_at = datetime.utcnow()
        enrollment.next_action_at = None


# ── Pause / Resume / Stop ─────────────────────────────────────────────────────

def pause_enrollment(db: Session, enrollment: DoctorPipelineEnrollment, reason: str = ""):
    enrollment.status = DoctorStatus.paused
    enrollment.paused_reason = reason
    db.flush()


def resume_enrollment(db: Session, enrollment: DoctorPipelineEnrollment):
    enrollment.status = DoctorStatus.active
    enrollment.paused_reason = None
    if enrollment.next_action_at is None:
        enrollment.next_action_at = datetime.utcnow()
    db.flush()


def stop_enrollment(db: Session, enrollment: DoctorPipelineEnrollment):
    enrollment.status = DoctorStatus.stopped
    enrollment.next_action_at = None
    db.flush()
    # Opt the doctor out
    doctor = enrollment.doctor
    doctor.opted_out = True
    doctor.status = DoctorStatus.stopped
    # Cancel any pending or prepared executions
    for ex in enrollment.executions:
        if ex.status in (ExecutionStatus.pending, ExecutionStatus.prepared):
            ex.status = ExecutionStatus.skipped
            ex.error_message = "Doctor opted out"
    db.flush()


# ── Due-today helper (for dashboard / scheduler) ──────────────────────────────

def get_due_enrollments(db: Session) -> list[DoctorPipelineEnrollment]:
    """Return all active enrollments whose next_action_at is <= now for non-opted-out doctors."""
    now = datetime.utcnow()
    return (
        db.query(DoctorPipelineEnrollment)
        .join(Doctor, DoctorPipelineEnrollment.doctor_id == Doctor.id)
        .filter(
            DoctorPipelineEnrollment.status == DoctorStatus.active,
            DoctorPipelineEnrollment.next_action_at <= now,
            Doctor.opted_out == False,
        )
        .all()
    )
