"""Simple recovery API and task support endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.automation import acquire_task_lease
from app.database.database import get_db
from app.database.models import AutomationTask, AutomationTaskState, FailureCategory
from app.recovery.classifier import FailureClassifier, RecoveryKnowledgeBase, RecoveryPolicy

router = APIRouter()

_knowledge = RecoveryKnowledgeBase()
_knowledge.upsert(
    component="whatsapp",
    operation="send_message",
    error_signature="RATE_LIMIT",
    error_category=FailureCategory.RATE_LIMIT.value,
    strategy_type="DELAY_AND_RETRY",
    strategy_config={"base_delay": 30, "max_delay": 600, "max_attempts": 4},
    status="VERIFIED",
)
_knowledge.upsert(
    component="browser",
    operation="click",
    error_signature="ELEMENT_NOT_FOUND",
    error_category=FailureCategory.ELEMENT_NOT_FOUND.value,
    strategy_type="SEARCH_APPROVED_SELECTOR",
    strategy_config={"requires_human_review": True},
    status="VERIFIED",
)


class TaskCreateRequest(BaseModel):
    task_type: str
    doctor_id: int | None = None
    campaign_id: int | None = None
    enrollment_id: int | None = None
    current_step: str | None = None


class TaskOut(BaseModel):
    id: int
    task_type: str
    doctor_id: int | None = None
    campaign_id: int | None = None
    enrollment_id: int | None = None
    status: str
    current_step: str | None = None
    attempt_count: int = 0
    correlation_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorRequest(BaseModel):
    component: str
    operation: str
    message: str
    category: str | None = None
    outcome_uncertain: bool = False
    safe_to_repeat: bool = False
    correlation_id: str | None = None


@router.get("/health")
def health():
    return {"status": "ok", "service": "automation"}


@router.post("/tasks", response_model=TaskOut)
def create_task(payload: TaskCreateRequest, db: Session = Depends(get_db)):
    task = AutomationTask(
        task_type=payload.task_type,
        doctor_id=payload.doctor_id,
        campaign_id=payload.campaign_id,
        enrollment_id=payload.enrollment_id,
        status=AutomationTaskState.PENDING.value,
        current_step=payload.current_step,
        correlation_id=str(uuid.uuid4()),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(AutomationTask).order_by(AutomationTask.created_at.desc()).all()
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(AutomationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/tasks/{task_id}/lease")
def lease_task(task_id: int, owner: str = "worker", db: Session = Depends(get_db)):
    task = acquire_task_lease(db, task_id, owner)
    return {"task_id": task.id, "lease_owner": task.lease_owner, "lease_expires_at": task.lease_expires_at}


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(AutomationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = AutomationTaskState.CANCELLED.value
    task.updated_at = datetime.utcnow()
    db.add(task)
    db.commit()
    return {"status": "cancelled", "task_id": task.id}


@router.post("/classify")
def classify_error(payload: ErrorRequest):
    error = FailureClassifier.classify(
        {"category": payload.category, "message": payload.message, "outcome_uncertain": payload.outcome_uncertain, "safe_to_repeat": payload.safe_to_repeat, "correlation_id": payload.correlation_id},
        component=payload.component,
        operation=payload.operation,
    )
    return error.to_dict()


@router.post("/recovery-policy")
def recovery_policy(payload: ErrorRequest, attempt_count: int = 1):
    error = FailureClassifier.classify(
        {"category": payload.category, "message": payload.message, "outcome_uncertain": payload.outcome_uncertain, "safe_to_repeat": payload.safe_to_repeat, "correlation_id": payload.correlation_id},
        component=payload.component,
        operation=payload.operation,
    )
    decision = RecoveryPolicy().decide(error, attempt_count, action_safe_to_repeat=payload.safe_to_repeat)
    return {"retry": decision.retry, "delay_seconds": decision.delay_seconds, "reason": decision.reason, "next_state": decision.next_state}


@router.get("/knowledge")
def knowledge(component: str, operation: str | None = None):
    return _knowledge.search(component=component, operation=operation)
