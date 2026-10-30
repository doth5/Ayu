"""Templates API router."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import MessageTemplate
from app.core.template_engine import extract_placeholders

router = APIRouter()


class TemplateCreate(BaseModel):
    name: str
    content: str
    specialty: Optional[str] = None
    tags: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    specialty: Optional[str] = None
    tags: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateOut(BaseModel):
    id: int
    name: str
    content: str
    specialty: Optional[str]
    tags: Optional[str]
    is_active: bool
    placeholders: list[str] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


def _enrich(tmpl: MessageTemplate) -> dict:
    d = {c.key: getattr(tmpl, c.key) for c in tmpl.__table__.columns}
    d["placeholders"] = extract_placeholders(tmpl.content)
    return d


@router.get("", response_model=list[TemplateOut])
def list_templates(
    specialty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(MessageTemplate).filter_by(is_active=True)
    if specialty:
        q = q.filter(
            (MessageTemplate.specialty == specialty) | (MessageTemplate.specialty == None)
        )
    if search:
        q = q.filter(MessageTemplate.name.ilike(f"%{search}%"))
    results = q.order_by(MessageTemplate.specialty, MessageTemplate.name).all()
    return [_enrich(t) for t in results]


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    tmpl = MessageTemplate(**payload.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return _enrich(tmpl)


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.get(MessageTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    return _enrich(tmpl)


@router.patch("/{template_id}", response_model=TemplateOut)
def update_template(template_id: int, payload: TemplateUpdate, db: Session = Depends(get_db)):
    tmpl = db.get(MessageTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(tmpl, field, value)
    db.commit()
    db.refresh(tmpl)
    return _enrich(tmpl)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.get(MessageTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    db.delete(tmpl)
    db.commit()


@router.post("/{template_id}/preview")
def preview_template(
    template_id: int,
    context: dict,
    db: Session = Depends(get_db),
):
    """Render a template with given context for preview."""
    from app.core.template_engine import render_template
    tmpl = db.get(MessageTemplate, template_id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    rendered = render_template(tmpl.content, context)
    return {"rendered": rendered}
