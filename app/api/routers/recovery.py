"""Structured recovery and operational endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import RecoveryKnowledge

router = APIRouter()


class RecoveryKnowledgeIn(BaseModel):
    component: str
    operation: str
    error_signature: str | None = None
    error_category: str | None = None
    root_cause: str | None = None
    strategy_type: str = "DELAY_AND_RETRY"
    strategy_config: dict | None = None
    preconditions: list[str] | None = None
    verification_method: str | None = None
    status: str = "VERIFIED"


@router.get("/health")
def health():
    return {"status": "ok", "service": "recovery"}


@router.post("/knowledge")
def create_recovery_knowledge(payload: RecoveryKnowledgeIn, db: Session = Depends(get_db)):
    item = RecoveryKnowledge(
        component=payload.component,
        operation=payload.operation,
        error_signature=payload.error_signature,
        error_category=payload.error_category,
        root_cause=payload.root_cause,
        strategy_type=payload.strategy_type,
        strategy_config=(payload.strategy_config and str(payload.strategy_config)) or None,
        preconditions=(payload.preconditions and str(payload.preconditions)) or None,
        verification_method=payload.verification_method,
        status=payload.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "status": item.status}


@router.get("/knowledge")
def list_recovery_knowledge(db: Session = Depends(get_db)):
    return db.query(RecoveryKnowledge).order_by(RecoveryKnowledge.created_at.desc()).all()
