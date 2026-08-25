from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class SubscriptionCaseModel(Base):
    __tablename__ = "subscription_cases"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), default="Demo customer")
    status: Mapped[str] = mapped_column(String(32), index=True)
    failure_reason: Mapped[str] = mapped_column(String(48), default="unknown")
    amount_paise: Mapped[int] = mapped_column(Integer)
    days_overdue: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    prior_successes: Mapped[int] = mapped_column(Integer, default=0)
    previous_interventions: Mapped[int] = mapped_column(Integer, default=0)
    contacts_7d: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovered_amount_paise: Mapped[int] = mapped_column(Integer, default=0)
    active_recovery_link_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active_recovery_link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_event_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    proposals: Mapped[list["RecoveryProposalModel"]] = relationship(back_populates="case")


class WebhookEventModel(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    event_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecoveryProposalModel(Base):
    __tablename__ = "recovery_proposals"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("subscription_cases.id"), index=True)
    recommended_action: Mapped[str] = mapped_column(String(48))
    model_recommended_action: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    message_english: Mapped[str] = mapped_column(Text, default="")
    message_hinglish: Mapped[str] = mapped_column(Text, default="")
    expected_value_rupees: Mapped[float] = mapped_column(Float, default=0)
    action_scores_json: Mapped[str] = mapped_column(Text, default="{}")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(32), default="proposed", index=True)
    policy_reason: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(48), default="deterministic-fallback")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[SubscriptionCaseModel] = relationship(back_populates="proposals")


class ActionExecutionModel(Base):
    __tablename__ = "action_executions"
    __table_args__ = (UniqueConstraint("case_id", "action", name="uq_case_action"),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("subscription_cases.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("recovery_proposals.id"), index=True)
    action: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    adapter: Mapped[str] = mapped_column(String(24), default="demo")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    label: Mapped[str] = mapped_column(String(100), default="10 × 200 held-out synthetic cases")
    summary_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
