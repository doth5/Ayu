"""
SQLAlchemy models for AyuSynk Sales Pipeline.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Enums ────────────────────────────────────────────────────────────────────

class SpecialtyEnum(str, enum.Enum):
    general_physician   = "General Physician"
    pediatrician        = "Pediatrician"
    cardiologist        = "Cardiologist"
    pulmonologist       = "Pulmonologist"
    surgeon             = "Surgeon"
    anesthesiologist    = "Anesthesiologist"
    orthopedic          = "Orthopedic"
    emergency_medicine  = "Emergency Medicine"
    gynecologist        = "Gynecologist"
    medical_student     = "Medical Student"
    professor           = "Professor"


class DoctorStatus(str, enum.Enum):
    active    = "active"
    paused    = "paused"
    stopped   = "stopped"
    completed = "completed"


class StepType(str, enum.Enum):
    text     = "text"
    image    = "image"
    video    = "video"
    document = "document"
    mixed    = "mixed"   # text + media


class ExecutionStatus(str, enum.Enum):
    pending   = "pending"
    prepared  = "prepared"
    sent      = "sent"
    failed    = "failed"
    skipped   = "skipped"
    replied   = "replied"


class CampaignStatus(str, enum.Enum):
    draft     = "draft"
    running   = "running"
    paused    = "paused"
    completed = "completed"
    cancelled = "cancelled"


class RecipientStatus(str, enum.Enum):
    pending  = "pending"
    sending  = "sending"
    sent     = "sent"
    failed   = "failed"
    skipped  = "skipped"


class MediaType(str, enum.Enum):
    image    = "image"
    video    = "video"
    pdf      = "pdf"
    document = "document"
    audio    = "audio"


# ── Models ────────────────────────────────────────────────────────────────────

class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    clinic_name: Mapped[Optional[str]] = mapped_column(String(200))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=DoctorStatus.active)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    enrollments: Mapped[list["DoctorPipelineEnrollment"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    message_logs: Mapped[list["MessageLog"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    steps: Mapped[list["PipelineStep"]] = relationship(
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStep.step_order",
    )
    enrollments: Mapped[list["DoctorPipelineEnrollment"]] = relationship(
        back_populates="pipeline"
    )


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[Optional[str]] = mapped_column(String(100))   # None = universal
    tags: Mapped[Optional[str]] = mapped_column(String(500))         # comma-separated
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    pipeline_steps: Mapped[list["PipelineStep"]] = relationship(
        back_populates="template"
    )


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    specialty: Mapped[Optional[str]] = mapped_column(String(100))   # None = universal
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pipeline_steps: Mapped[list["PipelineStep"]] = relationship(
        back_populates="media_file"
    )


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "step_order", name="uq_pipeline_step_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), default=StepType.text)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("message_templates.id"))
    media_file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_files.id"))
    # Delay AFTER the previous step before this step becomes eligible
    delay_hours: Mapped[float] = mapped_column(Float, default=0.0)
    # Conditions: JSON string. e.g. {"require_no_reply": true}
    conditions: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    pipeline: Mapped["Pipeline"] = relationship(back_populates="steps")
    template: Mapped[Optional["MessageTemplate"]] = relationship(back_populates="pipeline_steps")
    media_file: Mapped[Optional["MediaFile"]] = relationship(back_populates="pipeline_steps")


class DoctorPipelineEnrollment(Base):
    """Tracks which pipeline a doctor is enrolled in and their current progress."""
    __tablename__ = "doctor_pipeline_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    pipeline_id: Mapped[int] = mapped_column(ForeignKey("pipelines.id"), nullable=False)
    current_step_order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default=DoctorStatus.active)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    next_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    paused_reason: Mapped[Optional[str]] = mapped_column(Text)

    doctor: Mapped["Doctor"] = relationship(back_populates="enrollments")
    pipeline: Mapped["Pipeline"] = relationship(back_populates="enrollments")
    executions: Mapped[list["PipelineExecution"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan"
    )


class PipelineExecution(Base):
    """One record per pipeline step execution attempt."""
    __tablename__ = "pipeline_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("doctor_pipeline_enrollments.id"), nullable=False
    )
    step_id: Mapped[int] = mapped_column(ForeignKey("pipeline_steps.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ExecutionStatus.pending)
    rendered_message: Mapped[Optional[str]] = mapped_column(Text)
    media_path: Mapped[Optional[str]] = mapped_column(String(500))
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(200))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    prepared_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    enrollment: Mapped["DoctorPipelineEnrollment"] = relationship(back_populates="executions")
    step: Mapped["PipelineStep"] = relationship()


class MessageLog(Base):
    """Complete audit trail of every send attempt."""
    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    execution_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pipeline_executions.id"))
    direction: Mapped[str] = mapped_column(String(10), default="outbound")  # outbound / inbound
    message_content: Mapped[Optional[str]] = mapped_column(Text)
    media_path: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(200))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    doctor: Mapped["Doctor"] = relationship(back_populates="message_logs")


# ── Bulk Campaign Models ──────────────────────────────────────────────────────

class BulkCampaign(Base):
    """Stores a single bulk-messaging campaign with its config and current run state."""
    __tablename__ = "bulk_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    # Message type: text | image | pdf | video | docx | link
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    text_message: Mapped[Optional[str]] = mapped_column(Text)
    # Caption shown with media attachments
    caption: Mapped[Optional[str]] = mapped_column(Text)
    # Absolute path to the uploaded file (if any)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_name: Mapped[Optional[str]] = mapped_column(String(300))
    # Delay range in seconds between sequential sends
    delay_min: Mapped[int] = mapped_column(Integer, default=10)
    delay_max: Mapped[int] = mapped_column(Integer, default=20)
    # Campaign run state
    status: Mapped[str] = mapped_column(String(20), default=CampaignStatus.draft)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    current_recipient_index: Mapped[int] = mapped_column(Integer, default=0)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    recipients: Mapped[list["BulkCampaignRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan",
        order_by="BulkCampaignRecipient.id"
    )


class BulkCampaignRecipient(Base):
    """One row per doctor in a BulkCampaign – tracks per-recipient send status."""
    __tablename__ = "bulk_campaign_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("bulk_campaigns.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    # Snapshot of doctor details at campaign creation time
    doctor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RecipientStatus.pending)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    campaign: Mapped["BulkCampaign"] = relationship(back_populates="recipients")
    doctor: Mapped["Doctor"] = relationship()
