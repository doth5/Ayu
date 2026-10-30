"""Media files API router – upload, list, delete."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import MediaFile, MediaType
from config.settings import settings

router = APIRouter()

ALLOWED_MIME = {
    "image":    ["image/jpeg", "image/png", "image/webp", "image/gif"],
    "video":    ["video/mp4", "video/mpeg", "video/quicktime"],
    "pdf":      ["application/pdf"],
    "document": ["application/pdf", "application/msword",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    "audio":    ["audio/mpeg", "audio/wav", "audio/ogg"],
}

MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


class MediaOut(BaseModel):
    id: int
    name: str
    media_type: str
    file_path: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    specialty: Optional[str]
    description: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[MediaOut])
def list_media(
    media_type: Optional[str] = None,
    specialty: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(MediaFile)
    if media_type:
        q = q.filter_by(media_type=media_type)
    if specialty:
        q = q.filter(
            (MediaFile.specialty == specialty) | (MediaFile.specialty == None)
        )
    return q.order_by(MediaFile.created_at.desc()).all()


@router.post("", response_model=MediaOut, status_code=201)
async def upload_media(
    name: str = Form(...),
    media_type: str = Form(...),
    specialty: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if media_type not in [e.value for e in MediaType]:
        raise HTTPException(400, f"media_type must be one of {[e.value for e in MediaType]}")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB} MB limit")

    # Save to organised folder
    folder = settings.MEDIA_ROOT / media_type
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "file").suffix or ""
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = folder / filename
    dest.write_bytes(content)

    rel_path = str(dest.relative_to(settings.MEDIA_ROOT.parent))

    record = MediaFile(
        name=name,
        media_type=media_type,
        file_path=str(dest),
        file_size_bytes=len(content),
        mime_type=file.content_type,
        specialty=specialty,
        description=description,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{media_id}", response_model=MediaOut)
def get_media(media_id: int, db: Session = Depends(get_db)):
    m = db.get(MediaFile, media_id)
    if not m:
        raise HTTPException(404, "Media file not found")
    return m


@router.delete("/{media_id}", status_code=204)
def delete_media(media_id: int, db: Session = Depends(get_db)):
    m = db.get(MediaFile, media_id)
    if not m:
        raise HTTPException(404, "Media file not found")
    # Remove file from disk
    try:
        os.remove(m.file_path)
    except FileNotFoundError:
        pass
    db.delete(m)
    db.commit()
