"""Automation lease helpers and task-state primitives."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.models import AutomationTask, AutomationTaskState
from config.settings import settings


def is_lease_valid(task: AutomationTask, now: datetime | None = None) -> bool:
    if task.lease_expires_at is None:
        return False
    if task.status not in {AutomationTaskState.RUNNING.value, AutomationTaskState.READY.value}:
        return False
    now = now or datetime.utcnow()
    return task.lease_expires_at >= now


def acquire_task_lease(db: Session, task_id: int, owner: str, lease_seconds: int | None = None) -> AutomationTask:
    lease_seconds = lease_seconds or settings.TASK_LEASE_SECONDS
    task = db.get(AutomationTask, task_id)
    if task is None:
        raise ValueError(f"Automation task {task_id} not found")

    now = datetime.utcnow()
    expiry = now + timedelta(seconds=lease_seconds)
    task.status = AutomationTaskState.RUNNING.value
    task.lease_owner = owner
    task.lease_expires_at = expiry
    task.updated_at = now
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def release_task_lease(db: Session, task_id: int, owner: str | None = None) -> AutomationTask:
    task = db.get(AutomationTask, task_id)
    if task is None:
        raise ValueError(f"Automation task {task_id} not found")
    if owner and task.lease_owner and task.lease_owner != owner:
        raise PermissionError("lease owner mismatch")
    task.lease_owner = None
    task.lease_expires_at = None
    task.updated_at = datetime.utcnow()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
