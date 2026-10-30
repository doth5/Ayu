"""Pipelines API router."""
from __future__ import annotations

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Pipeline, PipelineStep, MessageTemplate, MediaFile, StepType

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class StepOut(BaseModel):
    id: int
    step_order: int
    name: str
    step_type: str
    template_id: Optional[int]
    media_file_id: Optional[int]
    delay_hours: float
    conditions: Optional[str]
    is_active: bool
    model_config = {"from_attributes": True}


class PipelineOut(BaseModel):
    id: int
    name: str
    specialty: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    steps: list[StepOut] = []
    model_config = {"from_attributes": True}


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class StepCreate(BaseModel):
    step_order: int
    name: str
    step_type: str = StepType.text
    template_id: Optional[int] = None
    media_file_id: Optional[int] = None
    delay_hours: float = 0.0
    conditions: Optional[str] = None
    is_active: bool = True


class StepUpdate(BaseModel):
    step_order: Optional[int] = None
    name: Optional[str] = None
    step_type: Optional[str] = None
    template_id: Optional[int] = None
    media_file_id: Optional[int] = None
    delay_hours: Optional[float] = None
    conditions: Optional[str] = None
    is_active: Optional[bool] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PipelineOut])
def list_pipelines(db: Session = Depends(get_db)):
    return db.query(Pipeline).order_by(Pipeline.specialty).all()


@router.get("/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")
    return p


@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(pipeline_id: int, payload: PipelineUpdate, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


# ── Step management ───────────────────────────────────────────────────────────

@router.post("/{pipeline_id}/steps", response_model=StepOut, status_code=201)
def add_step(pipeline_id: int, payload: StepCreate, db: Session = Depends(get_db)):
    p = db.get(Pipeline, pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")

    # Validate references
    if payload.template_id:
        if not db.get(MessageTemplate, payload.template_id):
            raise HTTPException(400, "Template not found")
    if payload.media_file_id:
        if not db.get(MediaFile, payload.media_file_id):
            raise HTTPException(400, "Media file not found")

    step = PipelineStep(pipeline_id=pipeline_id, **payload.model_dump())
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.patch("/{pipeline_id}/steps/{step_id}", response_model=StepOut)
def update_step(
    pipeline_id: int, step_id: int, payload: StepUpdate, db: Session = Depends(get_db)
):
    step = db.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(404, "Step not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(step, field, value)
    db.commit()
    db.refresh(step)
    return step


@router.delete("/{pipeline_id}/steps/{step_id}", status_code=204)
def delete_step(pipeline_id: int, step_id: int, db: Session = Depends(get_db)):
    step = db.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(404, "Step not found")
    db.delete(step)
    db.commit()


@router.post("/{pipeline_id}/steps/reorder")
def reorder_steps(pipeline_id: int, order: list[int], db: Session = Depends(get_db)):
    """Reorder steps. `order` is a list of step IDs in desired order."""
    for idx, step_id in enumerate(order, start=1):
        step = db.get(PipelineStep, step_id)
        if step and step.pipeline_id == pipeline_id:
            step.step_order = idx
    db.commit()
    return {"message": "Steps reordered"}
