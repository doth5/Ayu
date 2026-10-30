"""
SQLAlchemy models for AyuSynk Sales Pipeline.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SpecialtyEnum(str, enum.Enum):
    general_physician = "General Physician"
    pediatrician = "Pediatrician"
    cardiologist = "Cardiologist"
    pulmonologist = "Pulmonologist"
    surgeon = "Surgeon"
    anesthesiologist = "Anesthesiologist"
    orthopedic = "Orthopedic"
    emergency_medicine = "Emergency Medicine"
    gynecologist = "Gynecologist"
    medical_student = "Medical Student"
    professor = "Professor"


class DoctorStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    stopped = "stopped"
    completed = "completed"


class StepType(str, enum.Enum):
    text = "text"
    image = "image"
    video = "video"
    document = "document"
    mixed = "mixed"


class ExecutionStatus(str, enum.Enum):
    pending = "pending"
    prepared = "prepared"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"
    replied = "replied"


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"


class RecipientStatus(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class MediaType(str, enum.Enum):
    image = "image"
    video = "video"
    pdf = "pdf"
    document = "document"
    audio = "audio"


class AutomationTaskState(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_RETRY = "WAITING_RETRY"
    WAITING_EXTERNAL_EVENT = "WAITING_EXTERNAL_EVENT"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FailureCategory(str, enum.Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    CONSENT_BLOCK = "CONSENT_BLOCK"
    OPT_OUT_BLOCK = "OPT_OUT_BLOCK"
    RATE_LIMIT = "RATE_LIMIT"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION_ERROR = "NETWORK_CONNECTION_ERROR"
    PROVIDER_SERVER_ERROR = "PROVIDER_SERVER_ERROR"
    PROVIDER_REJECTION = "PROVIDER_REJECTION"
    WEBHOOK_PROCESSING_ERROR = "WEBHOOK_PROCESSING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    REDIS_ERROR = "REDIS_ERROR"
    WORKER_CRASH = "WORKER_CRASH"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    ELEMENT_NOT_ACTIONABLE = "ELEMENT_NOT_ACTIONABLE"
    PAGE_STATE_MISMATCH = "PAGE_STATE_MISMATCH"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SELECTOR_STALE = "SELECTOR_STALE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class AutomationActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    CANCELLED = "CANCELLED"


class RecoveryStatus(str, enum.Enum):
    OBSERVED = "OBSERVED"
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    VERIFIED = "VERIFIED"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"


class ProviderEventStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"
    INVALID = "INVALID"


class BrowserSelectorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    DISABLED = "DISABLED"


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
    enrollments: Mapped[list["DoctorPipelineEnrollment"]] = relationship(back_populates="pipeline")


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[Optional[str]] = mapped_column(String(100))
    tags: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    pipeline_steps: Mapped[list["PipelineStep"]] = relationship(back_populates="template")


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    specialty: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pipeline_steps: Mapped[list["PipelineStep"]] = relationship(back_populates="media_file")


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
    delay_hours: Mapped[float] = mapped_column(Float, default=0.0)
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
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("doctor_pipeline_enrollments.id"), nullable=False)
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
    direction: Mapped[str] = mapped_column(String(10), default="outbound")
    message_content: Mapped[Optional[str]] = mapped_column(Text)
    media_path: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(200))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    doctor: Mapped["Doctor"] = relationship(back_populates="message_logs")


class AutomationTask(Base):
    __tablename__ = "automation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    doctor_id: Mapped[Optional[int]] = mapped_column(Integer)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer)
    enrollment_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default=AutomationTaskState.PENDING)
    current_step: Mapped[Optional[str]] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(200))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error_category: Mapped[Optional[str]] = mapped_column(String(80))
    last_error_details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    actions: Mapped[list["AutomationAction"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    recovery_incidents: Mapped[list["RecoveryIncident"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class AutomationAction(Base):
    __tablename__ = "automation_actions"
    __table_args__ = (
        UniqueConstraint("task_id", "action_key", name="uq_automation_action_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("automation_tasks.id"), nullable=False)
    step_id: Mapped[Optional[str]] = mapped_column(String(100))
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_key: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(40), default=AutomationActionStatus.PENDING)
    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    external_reference: Mapped[Optional[str]] = mapped_column(String(200))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    verification_result: Mapped[Optional[str]] = mapped_column(String(80))
    error_category: Mapped[Optional[str]] = mapped_column(String(80))
    error_details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    task: Mapped["AutomationTask"] = relationship(back_populates="actions")
    attempts: Mapped[list["AutomationActionAttempt"]] = relationship(
        back_populates="action", cascade="all, delete-orphan"
    )


class AutomationActionAttempt(Base):
    __tablename__ = "automation_action_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("automation_actions.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    outcome: Mapped[Optional[str]] = mapped_column(String(80))
    error_category: Mapped[Optional[str]] = mapped_column(String(80))
    provider_error_code: Mapped[Optional[str]] = mapped_column(String(100))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    recovery_strategy_id: Mapped[Optional[int]] = mapped_column(Integer)
    verification_result: Mapped[Optional[str]] = mapped_column(String(80))

    action: Mapped["AutomationAction"] = relationship(back_populates="attempts")


class RecoveryKnowledge(Base):
    __tablename__ = "recovery_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    component: Mapped[str] = mapped_column(String(150), nullable=False)
    operation: Mapped[str] = mapped_column(String(150), nullable=False)
    error_signature: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    error_category: Mapped[Optional[str]] = mapped_column(String(80))
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    strategy_type: Mapped[str] = mapped_column(String(80), default="DELAY_AND_RETRY")
    strategy_config: Mapped[Optional[str]] = mapped_column(Text)
    preconditions: Mapped[Optional[str]] = mapped_column(Text)
    verification_method: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default=RecoveryStatus.OBSERVED)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RecoveryIncident(Base):
    __tablename__ = "recovery_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("automation_tasks.id"))
    action_id: Mapped[Optional[int]] = mapped_column(ForeignKey("automation_actions.id"))
    component: Mapped[str] = mapped_column(String(150), nullable=False)
    error_category: Mapped[str] = mapped_column(String(80), nullable=False)
    sanitized_evidence: Mapped[Optional[str]] = mapped_column(Text)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text)
    knowledge_record_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="OBSERVED")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    task: Mapped[Optional["AutomationTask"]] = relationship(back_populates="recovery_incidents")


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("recovery_incidents.id"), nullable=False)
    strategy_id: Mapped[Optional[int]] = mapped_column(Integer)
    attempt_number: Mapped[int] = mapped_column(Integer, default=0)
    proposed_action: Mapped[Optional[str]] = mapped_column(String(200))
    validation_result: Mapped[Optional[str]] = mapped_column(String(80))
    execution_result: Mapped[Optional[str]] = mapped_column(String(80))
    verification_result: Mapped[Optional[str]] = mapped_column(String(80))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ProviderEvent(Base):
    __tablename__ = "provider_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_provider_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[Optional[str]] = mapped_column(String(100))
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processing_status: Mapped[str] = mapped_column(String(40), default=ProviderEventStatus.RECEIVED)
    sanitized_payload: Mapped[Optional[str]] = mapped_column(Text)


class BrowserSelector(Base):
    __tablename__ = "browser_selectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application: Mapped[str] = mapped_column(String(150), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(200))
    page_signature_hash: Mapped[Optional[str]] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(String(150), nullable=False)
    selector: Mapped[str] = mapped_column(String(500), nullable=False)
    strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(40), default=BrowserSelectorStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AutomationControl(Base):
    __tablename__ = "automation_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scope: Mapped[str] = mapped_column(String(60), nullable=False)
    scope_reference: Mapped[Optional[str]] = mapped_column(String(200))
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[str]] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BulkCampaign(Base):
    """Stores a single bulk-messaging campaign with its config and current run state."""

    __tablename__ = "bulk_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    text_message: Mapped[Optional[str]] = mapped_column(Text)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_name: Mapped[Optional[str]] = mapped_column(String(300))
    delay_min: Mapped[int] = mapped_column(Integer, default=10)
    delay_max: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(20), default=CampaignStatus.draft)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    current_recipient_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    recipients: Mapped[list["BulkCampaignRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="BulkCampaignRecipient.id"
    )


class BulkCampaignRecipient(Base):
    """One row per doctor in a BulkCampaign – tracks per-recipient send status."""

    __tablename__ = "bulk_campaign_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("bulk_campaigns.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    doctor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RecipientStatus.pending)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    campaign: Mapped["BulkCampaign"] = relationship(back_populates="recipients")
    doctor: Mapped["Doctor"] = relationship()


__all__ = [
    "Base",
    "Doctor",
    "Pipeline",
    "MessageTemplate",
    "MediaFile",
    "PipelineStep",
    "DoctorPipelineEnrollment",
    "PipelineExecution",
    "MessageLog",
    "BulkCampaign",
    "BulkCampaignRecipient",
    "AutomationTask",
    "AutomationAction",
    "AutomationActionAttempt",
    "RecoveryKnowledge",
    "RecoveryIncident",
    "RecoveryAttempt",
    "ProviderEvent",
    "BrowserSelector",
    "AutomationControl",
    "AutomationTaskState",
    "FailureCategory",
    "AutomationActionStatus",
    "RecoveryStatus",
    "ProviderEventStatus",
    "BrowserSelectorStatus",
    "DoctorStatus",
    "StepType",
    "ExecutionStatus",
    "CampaignStatus",
    "RecipientStatus",
    "MediaType",
    "SpecialtyEnum",
]

