"""Doctors API router."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Doctor, DoctorStatus, SpecialtyEnum, ExecutionStatus
from app.core.pipeline_engine import (
    enrol_doctor, pause_enrollment, resume_enrollment, stop_enrollment,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    name: str
    mobile: str
    specialty: str
    clinic_name: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("Doctor name cannot be empty")
        return v

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v):
        valid = [e.value for e in SpecialtyEnum]
        if v not in valid:
            raise ValueError(f"Specialty must be one of: {valid}")
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v):
        cleaned = v.strip().replace(" ", "").replace("-", "")
        if not cleaned.startswith("+"):
            raise ValueError("Mobile number must include country code starting with '+' (e.g. +91...)")
        if not cleaned[1:].isdigit():
            raise ValueError("Mobile number must contain only digits after '+'")
        if len(cleaned[1:]) < 10:
            raise ValueError("Mobile number must have at least 10 digits after the country code")
        return cleaned


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    specialty: Optional[str] = None
    clinic_name: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    opted_out: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Doctor name cannot be empty")
        return v

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v):
        if v is not None:
            valid = [e.value for e in SpecialtyEnum]
            if v not in valid:
                raise ValueError(f"Specialty must be one of: {valid}")
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v):
        if v is not None:
            cleaned = v.strip().replace(" ", "").replace("-", "")
            if not cleaned.startswith("+"):
                raise ValueError("Mobile number must include country code starting with '+' (e.g. +91...)")
            if not cleaned[1:].isdigit():
                raise ValueError("Mobile number must contain only digits after '+'")
            if len(cleaned[1:]) < 10:
                raise ValueError("Mobile number must have at least 10 digits after the country code")
            return cleaned
        return v


class DoctorOut(BaseModel):
    id: int
    name: str
    mobile: str
    specialty: str
    clinic_name: Optional[str]
    city: Optional[str]
    notes: Optional[str]
    status: str
    opted_out: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DoctorOut])
def list_doctors(
    specialty: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    opted_out: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Doctor)
    if specialty and specialty != "All":
        q = q.filter(Doctor.specialty == specialty)
    if status and status != "All":
        q = q.filter(Doctor.status == status)
    if opted_out is not None:
        q = q.filter(Doctor.opted_out == opted_out)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(
            Doctor.name.ilike(s)
            | Doctor.mobile.ilike(s)
            | Doctor.city.ilike(s)
            | Doctor.clinic_name.ilike(s)
        )
    return q.order_by(Doctor.created_at.desc()).all()


@router.post("", response_model=DoctorOut, status_code=201)
def add_doctor(payload: DoctorCreate, db: Session = Depends(get_db)):
    # Check duplicate mobile
    existing = db.query(Doctor).filter_by(mobile=payload.mobile).first()
    if existing:
        raise HTTPException(400, f"Doctor with mobile '{payload.mobile}' already exists ({existing.name}).")

    doctor = Doctor(**payload.model_dump())
    db.add(doctor)
    db.flush()

    # Auto-enrol in specialty pipeline
    enrol_doctor(db, doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    return d


@router.patch("/{doctor_id}", response_model=DoctorOut)
def update_doctor(doctor_id: int, payload: DoctorUpdate, db: Session = Depends(get_db)):
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")

    data = payload.model_dump(exclude_unset=True)

    # 1. Check duplicate mobile if changed
    if "mobile" in data and data["mobile"] is not None:
        new_mobile = data["mobile"]
        if new_mobile != d.mobile:
            existing = db.query(Doctor).filter(Doctor.mobile == new_mobile, Doctor.id != doctor_id).first()
            if existing:
                raise HTTPException(400, f"Another doctor ({existing.name}) already has mobile '{new_mobile}'.")
            d.mobile = new_mobile

    # 2. Check specialty change & manage pipeline enrollment
    if "specialty" in data and data["specialty"] is not None:
        new_spec = data["specialty"]
        if new_spec != d.specialty:
            d.specialty = new_spec
            # If not opted out, transition old active enrollments and enrol in new specialty pipeline
            if not d.opted_out:
                for enr in d.enrollments:
                    if enr.status in (DoctorStatus.active, DoctorStatus.paused):
                        enr.status = DoctorStatus.completed
                        enr.next_action_at = None
                enrol_doctor(db, d)

    # 3. Handle opt-out state change
    if "opted_out" in data and data["opted_out"] is not None:
        new_opted_out = bool(data["opted_out"])
        if new_opted_out and not d.opted_out:
            # Transition to Opted Out
            d.opted_out = True
            d.status = DoctorStatus.stopped
            for enr in d.enrollments:
                if enr.status in (DoctorStatus.active, DoctorStatus.paused):
                    enr.status = DoctorStatus.stopped
                    enr.next_action_at = None
                for ex in enr.executions:
                    if ex.status in (ExecutionStatus.pending, ExecutionStatus.prepared):
                        ex.status = ExecutionStatus.skipped
                        ex.error_message = "Doctor opted out"
        elif not new_opted_out and d.opted_out:
            # Transition back to Opted In
            d.opted_out = False
            d.status = DoctorStatus.active
            resumed = False
            for enr in d.enrollments:
                if enr.status == DoctorStatus.stopped:
                    enr.status = DoctorStatus.active
                    enr.next_action_at = datetime.utcnow()
                    resumed = True
                    break
            if not resumed:
                enrol_doctor(db, d)

    # 4. Update remaining attributes
    for field in ("name", "clinic_name", "city", "notes", "status"):
        if field in data and data[field] is not None:
            setattr(d, field, data[field])

    d.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    return d


@router.delete("/{doctor_id}", status_code=200)
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    name = d.name
    db.delete(d)
    db.commit()
    return {"status": "deleted", "doctor_id": doctor_id, "name": name}


# ── Opt-out & Opt-in Endpoints ───────────────────────────────────────────────

@router.post("/{doctor_id}/opt-out", response_model=DoctorOut)
def opt_out_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Opt a doctor out of all WhatsApp messaging and campaigns."""
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")

    d.opted_out = True
    d.status = DoctorStatus.stopped
    for enr in d.enrollments:
        if enr.status in (DoctorStatus.active, DoctorStatus.paused):
            enr.status = DoctorStatus.stopped
            enr.next_action_at = None
        for ex in enr.executions:
            if ex.status in (ExecutionStatus.pending, ExecutionStatus.prepared):
                ex.status = ExecutionStatus.skipped
                ex.error_message = "Doctor opted out"

    d.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    return d


@router.post("/{doctor_id}/opt-in", response_model=DoctorOut)
def opt_in_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Opt a doctor back in and re-activate outreach eligibility."""
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")

    d.opted_out = False
    d.status = DoctorStatus.active
    resumed = False
    for enr in d.enrollments:
        if enr.status == DoctorStatus.stopped:
            enr.status = DoctorStatus.active
            enr.next_action_at = datetime.utcnow()
            resumed = True
            break
    if not resumed:
        enrol_doctor(db, d)

    d.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(d)
    return d


# ── Pipeline control ──────────────────────────────────────────────────────────

@router.post("/{doctor_id}/pause")
def pause_doctor_pipeline(doctor_id: int, reason: str = "", db: Session = Depends(get_db)):
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    for enrollment in d.enrollments:
        if enrollment.status == DoctorStatus.active:
            pause_enrollment(db, enrollment, reason)
    db.commit()
    return {"message": "Pipeline paused"}


@router.post("/{doctor_id}/resume")
def resume_doctor_pipeline(doctor_id: int, db: Session = Depends(get_db)):
    d = db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    if d.opted_out:
        raise HTTPException(400, "Cannot resume pipeline for an opted-out doctor. Please opt them back in first.")
    for enrollment in d.enrollments:
        if enrollment.status == DoctorStatus.paused:
            resume_enrollment(db, enrollment)
    db.commit()
    return {"message": "Pipeline resumed"}


@router.post("/{doctor_id}/stop")
def stop_doctor_pipeline(doctor_id: int, db: Session = Depends(get_db)):
    return opt_out_doctor(doctor_id=doctor_id, db=db)

