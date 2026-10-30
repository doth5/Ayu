"""Dashboard API – aggregated stats for the Streamlit dashboard."""
from __future__ import annotations

from datetime import datetime, date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import (
    Doctor, DoctorPipelineEnrollment, PipelineExecution,
    DoctorStatus, ExecutionStatus, MessageLog,
)

router = APIRouter()


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_doctors = db.query(func.count(Doctor.id)).scalar()
    by_specialty = (
        db.query(Doctor.specialty, func.count(Doctor.id))
        .group_by(Doctor.specialty)
        .all()
    )

    active_pipelines = (
        db.query(func.count(DoctorPipelineEnrollment.id))
        .filter_by(status=DoctorStatus.active)
        .scalar()
    )
    paused_pipelines = (
        db.query(func.count(DoctorPipelineEnrollment.id))
        .filter_by(status=DoctorStatus.paused)
        .scalar()
    )
    completed_pipelines = (
        db.query(func.count(DoctorPipelineEnrollment.id))
        .filter_by(status=DoctorStatus.completed)
        .scalar()
    )

    now = datetime.utcnow()
    due_today = (
        db.query(func.count(DoctorPipelineEnrollment.id))
        .filter(
            DoctorPipelineEnrollment.status == DoctorStatus.active,
            DoctorPipelineEnrollment.next_action_at <= now,
        )
        .scalar()
    )

    pending_messages = (
        db.query(func.count(PipelineExecution.id))
        .filter_by(status=ExecutionStatus.prepared)
        .scalar()
    )
    sent_today = (
        db.query(func.count(PipelineExecution.id))
        .filter(
            PipelineExecution.status == ExecutionStatus.sent,
            func.date(PipelineExecution.sent_at) == date.today(),
        )
        .scalar()
    )
    failed = (
        db.query(func.count(PipelineExecution.id))
        .filter_by(status=ExecutionStatus.failed)
        .scalar()
    )

    opted_out = (
        db.query(func.count(Doctor.id)).filter_by(opted_out=True).scalar()
    )

    return {
        "total_doctors": total_doctors,
        "by_specialty": {row[0]: row[1] for row in by_specialty},
        "active_pipelines": active_pipelines,
        "paused_pipelines": paused_pipelines,
        "completed_pipelines": completed_pipelines,
        "due_today": due_today,
        "pending_messages": pending_messages,
        "sent_today": sent_today,
        "failed_executions": failed,
        "opted_out_doctors": opted_out,
    }


@router.get("/recent-logs")
def recent_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = (
        db.query(MessageLog)
        .order_by(MessageLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "doctor_name": log.doctor.name,
            "mobile": log.doctor.mobile,
            "direction": log.direction,
            "status": log.status,
            "message_preview": (log.message_content or "")[:100],
            "sent_at": log.sent_at,
            "created_at": log.created_at,
        }
        for log in logs
    ]
