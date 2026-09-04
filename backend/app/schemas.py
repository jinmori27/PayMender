from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class RecoveryAction(StrEnum):
    WAIT_FOR_RETRY = "WAIT_FOR_RETRY"
    REQUEST_PAYMENT_METHOD_UPDATE = "REQUEST_PAYMENT_METHOD_UPDATE"
    CREATE_RECOVERY_LINK = "CREATE_RECOVERY_LINK"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    STOP_CONTACT = "STOP_CONTACT"


class FailureReason(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    EXPIRED_CARD = "expired_card"
    ISSUER_DOWNTIME = "issuer_downtime"
    BANK_BLOCKED = "bank_blocked"
    MANDATE_CANCELLED = "mandate_cancelled"
    UNKNOWN = "unknown"


class ActionScore(BaseModel):
    action: RecoveryAction
    recovery_probability: float = Field(ge=0, le=1)
    expected_value_rupees: float
    allowed_by_model: bool = True


class GeminiDecision(BaseModel):
    diagnosis: FailureReason
    recommended_action: RecoveryAction
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=10, max_length=800)
    evidence: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        min_length=1,
        max_length=5,
    )
    message_english: str = Field(max_length=500)
    message_hinglish: str = Field(max_length=500)


class PolicyDecision(BaseModel):
    action: RecoveryAction
    allowed: bool
    requires_approval: bool
    reason: str
    overridden: bool = False


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subscription_id: str
    source: str
    enrichment_state: str
    provider_invoice_id: str | None
    provider_order_id: str | None
    customer_name: str
    status: str
    failure_reason: str
    amount_paise: int
    days_overdue: int
    retry_count: int
    prior_successes: int
    previous_interventions: int
    contacts_7d: int
    next_retry_at: datetime | None
    recovered_amount_paise: int
    active_recovery_link_id: str | None
    active_recovery_link_url: str | None
    created_at: datetime
    updated_at: datetime


class ProposalView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    recommended_action: RecoveryAction
    model_recommended_action: RecoveryAction
    confidence: float
    explanation: str
    evidence: list[str]
    message_english: str
    message_hinglish: str
    expected_value_rupees: float
    action_scores: list[ActionScore]
    requires_approval: bool
    state: str
    policy_reason: str
    provider: str
    created_at: datetime


class CaseDetail(CaseSummary):
    proposals: list[ProposalView] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(default="", max_length=300)


class AuditView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str | None
    category: str
    title: str
    detail: str
    severity: str
    metadata: dict[str, Any]
    created_at: datetime


class MetricsView(BaseModel):
    display_name: str
    demo_mode: bool
    total_cases: int
    at_risk_paise: int
    predicted_recoverable_paise: int
    recovered_paise: int
    pending_approvals: int
    stopped_cases: int
    escalated_cases: int
    blocked_actions: int


class WebhookReceipt(BaseModel):
    accepted: bool
    duplicate: bool = False
    event_id: str


class EvaluationPolicyMetrics(BaseModel):
    policy: str
    gross_recovered_mean: float
    gross_recovered_std: float
    net_recovered_mean: float
    net_recovered_std: float
    recovery_rate_mean: float
    contacts_per_recovery_mean: float
    escalation_rate_mean: float
    stopped_mean: float
    unsafe_blocked_mean: float


class EvaluationSummary(BaseModel):
    id: str
    label: str
    synthetic_disclaimer: str
    train_records: int
    batches: int
    cases_per_batch: int
    policies: list[EvaluationPolicyMetrics]
    created_at: datetime
