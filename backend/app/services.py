from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import Settings
from .evaluation import run_evaluation
from .gemini import GeminiAdvisor
from .ml import recovery_model
from .models import (
    ActionExecutionModel,
    AuditEventModel,
    EvaluationRunModel,
    JobModel,
    RecoveryProposalModel,
    SubscriptionCaseModel,
    WebhookEventModel,
    new_id,
    utcnow,
)
from .policy import decide_policy
from .razorpay import ProviderSubscriptionContext, RazorpayGateway
from .schemas import (
    ActionScore,
    AuditView,
    CaseDetail,
    CaseSummary,
    EvaluationSummary,
    MetricsView,
    ProposalView,
    RecoveryAction,
)


SUPPORTED_SUBSCRIPTION_EVENTS = {
    "subscription.pending",
    "subscription.halted",
    "subscription.charged",
    "subscription.cancelled",
    "subscription.completed",
}
SUPPORTED_EVENTS = SUPPORTED_SUBSCRIPTION_EVENTS | {"payment_link.paid"}
MAX_AMOUNT_PAISE = 1_000_000_000


def json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


def as_utc(value: datetime) -> datetime:
    """Normalize SQLite's timezone-naive datetimes before lifecycle comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def audit(
    db: Session,
    category: str,
    title: str,
    detail: str,
    *,
    case_id: str | None = None,
    severity: str = "info",
    metadata: dict | None = None,
) -> AuditEventModel:
    event = AuditEventModel(
        id=new_id("audit"),
        case_id=case_id,
        category=category,
        title=title,
        detail=detail,
        severity=severity,
        metadata_json=json_dumps(metadata or {}),
    )
    db.add(event)
    return event


def verify_webhook(raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def accept_webhook(
    db: Session,
    *,
    raw_body: bytes,
    signature: str,
    event_id: str,
    settings: Settings,
) -> tuple[bool, str]:
    if not event_id or len(event_id) > 120 or any(ord(character) < 32 for character in event_id):
        raise ValueError("Razorpay event id is invalid")
    if not settings.razorpay_webhook_secret:
        raise RuntimeError("Razorpay webhook secret is not configured")
    if not verify_webhook(raw_body, signature, settings.razorpay_webhook_secret):
        raise PermissionError("Invalid Razorpay webhook signature")

    payload = json.loads(raw_body)
    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be a JSON object")
    validate_webhook_payload(payload)
    event_type = str(payload.get("event", "unknown"))
    created_ts = payload.get("created_at")
    created_at = datetime.fromtimestamp(created_ts, timezone.utc) if isinstance(created_ts, (int, float)) else None
    model = WebhookEventModel(
        id=new_id("evt"),
        event_id=event_id,
        event_type=event_type,
        payload_json=raw_body.decode("utf-8"),
        event_created_at=created_at,
    )
    try:
        db.add(model)
        db.flush()
        db.add(JobModel(
            id=new_id("job"),
            kind="process_webhook",
            payload_json=json_dumps({"webhook_event_id": model.id}),
        ))
        audit(db, "webhook", "Webhook accepted", event_type, metadata={"event_id": event_id})
        db.commit()
        return False, model.id
    except IntegrityError:
        db.rollback()
        audit(db, "safety", "Duplicate webhook suppressed", "The same Razorpay event ID was already accepted.", metadata={"event_id": event_id})
        db.commit()
        return True, ""


def _entity(payload: dict, name: str) -> dict:
    container = payload.get("payload")
    if not isinstance(container, dict):
        return {}
    resource = container.get(name)
    if not isinstance(resource, dict):
        return {}
    entity = resource.get("entity")
    return entity if isinstance(entity, dict) else {}


def _validated_amount(value: Any, field_name: str) -> int:
    if value is None:
        raise ValueError(f"Webhook payload is missing {field_name}")
    try:
        amount = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Webhook {field_name} must be an integer") from exc
    if amount <= 0 or amount > MAX_AMOUNT_PAISE:
        raise ValueError(f"Webhook {field_name} is outside the permitted range")
    return amount


def normalize_payment_link_paid(payload: dict) -> dict:
    if str(payload.get("event", "")) != "payment_link.paid":
        raise ValueError("Webhook is not a Payment Link paid event")
    payment_link = _entity(payload, "payment_link")
    payment = _entity(payload, "payment")
    link_id = payment_link.get("id")
    payment_id = payment.get("id")
    notes_value = payment_link.get("notes") or {}
    notes = notes_value if isinstance(notes_value, dict) else {}
    case_id = notes.get("paymender_case_id")
    reference_id = payment_link.get("reference_id")

    if not isinstance(link_id, str) or not link_id.startswith("plink_") or len(link_id) > 120:
        raise ValueError("Payment Link webhook has an invalid link id")
    if not isinstance(payment_id, str) or not payment_id.strip() or len(payment_id) > 120:
        raise ValueError("Payment Link webhook has an invalid payment id")
    if not isinstance(case_id, str) or not case_id.startswith("case_") or len(case_id) > 48:
        raise ValueError("Payment Link webhook has an invalid PayMender case id")
    if not isinstance(reference_id, str) or not reference_id.strip() or len(reference_id) > 40:
        raise ValueError("Payment Link webhook has an invalid reference id")
    if payment_link.get("status") != "paid" or payment.get("status") != "captured":
        raise ValueError("Payment Link payment is not fully captured")
    if payment_link.get("currency") != "INR":
        raise ValueError("Payment Link currency must be INR")

    amount = _validated_amount(payment_link.get("amount"), "Payment Link amount")
    amount_paid = _validated_amount(payment_link.get("amount_paid"), "Payment Link amount paid")
    payment_amount = _validated_amount(payment.get("amount"), "captured payment amount")
    if amount != amount_paid or amount != payment_amount:
        raise ValueError("Payment Link payment amounts do not match")
    return {
        "case_id": case_id,
        "link_id": link_id,
        "payment_id": payment_id.strip(),
        "reference_id": reference_id.strip(),
        "amount_paise": amount,
    }


def _subscription_event_base(payload: dict) -> dict:
    event_type = str(payload.get("event", ""))
    if event_type not in SUPPORTED_SUBSCRIPTION_EVENTS:
        raise ValueError(f"Unsupported Razorpay event: {event_type or 'missing'}")
    subscription = _entity(payload, "subscription")
    payment = _entity(payload, "payment")
    invoice = _entity(payload, "invoice")
    payment_notes_value = payment.get("notes") or {}
    payment_notes = payment_notes_value if isinstance(payment_notes_value, dict) else {}
    demo_value = payload.get("demo") or {}
    demo = demo_value if isinstance(demo_value, dict) else {}
    subscription_id = (
        subscription.get("id")
        or invoice.get("subscription_id")
        or payment_notes.get("subscription_id")
        or demo.get("subscription_id")
    )
    if not isinstance(subscription_id, str) or not subscription_id.strip():
        raise ValueError("Webhook payload is missing a subscription id")
    subscription_id = subscription_id.strip()
    if len(subscription_id) > 80:
        raise ValueError("Webhook subscription id is too long")
    try:
        retry_count = int(subscription.get("auth_attempts", demo.get("retry_count", 1)))
        prior_successes = int(subscription.get("paid_count", demo.get("prior_successes", 0)))
        days_overdue = int(demo.get("days_overdue", 0))
        previous_interventions = int(demo.get("previous_interventions", 0))
        contacts_7d = int(demo.get("contacts_7d", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Webhook counters must be integers") from exc
    if min(retry_count, prior_successes, days_overdue, previous_interventions, contacts_7d) < 0:
        raise ValueError("Webhook counters cannot be negative")
    return {
        "subscription_id": subscription_id,
        "status": event_type.split(".", 1)[1],
        "retry_count": retry_count,
        "prior_successes": prior_successes,
        "days_overdue": days_overdue,
        "previous_interventions": previous_interventions,
        "contacts_7d": contacts_7d,
        "subscription": subscription,
        "payment": payment,
        "invoice": invoice,
        "demo": demo,
    }


def _embedded_amount(payload: dict) -> Any:
    base = _subscription_event_base(payload)
    subscription = base["subscription"]
    payment = base["payment"]
    invoice = base["invoice"]
    demo = base["demo"]
    notes_value = subscription.get("notes") or {}
    notes = notes_value if isinstance(notes_value, dict) else {}
    return payment.get("amount") or invoice.get("amount_due") or invoice.get("amount") or notes.get("amount_paise") or demo.get("amount_paise")


def validate_webhook_payload(payload: dict) -> None:
    event_type = str(payload.get("event", ""))
    if event_type not in SUPPORTED_EVENTS:
        raise ValueError(f"Unsupported Razorpay event: {event_type or 'missing'}")
    if event_type == "payment_link.paid":
        normalize_payment_link_paid(payload)
    else:
        _subscription_event_base(payload)


def normalize_webhook(
    payload: dict,
    provider_context: ProviderSubscriptionContext | None = None,
) -> dict:
    base = _subscription_event_base(payload)
    subscription = base["subscription"]
    payment = base["payment"]
    invoice = base["invoice"]
    notes_value = subscription.get("notes") or {}
    notes = notes_value if isinstance(notes_value, dict) else {}
    demo = base["demo"]
    subscription_id = base["subscription_id"]
    status = base["status"]
    if provider_context and provider_context.subscription_id != subscription_id:
        raise RuntimeError("Razorpay enrichment subscription does not match the webhook")
    amount_value = _embedded_amount(payload)
    if amount_value is None and provider_context:
        amount_value = provider_context.amount_paise
    amount = _validated_amount(amount_value, "outstanding amount")
    reason = (
        payment.get("error_reason")
        or payment.get("error_description")
        or (provider_context.failure_reason if provider_context else None)
        or notes.get("failure_reason")
        or demo.get("failure_reason")
        or "unknown"
    )
    reason_text = str(reason).lower()
    reason_map = {
        "insufficient": "insufficient_funds",
        "expired": "expired_card",
        "downtime": "issuer_downtime",
        "blocked": "bank_blocked",
        "mandate": "mandate_cancelled",
    }
    canonical_reason = next((value for token, value in reason_map.items() if token in reason_text), reason_text)
    if canonical_reason not in {"insufficient_funds", "expired_card", "issuer_downtime", "bank_blocked", "mandate_cancelled"}:
        canonical_reason = "unknown"

    next_charge_at = subscription.get("charge_at")
    next_retry = datetime.fromtimestamp(next_charge_at, timezone.utc) if next_charge_at and status == "pending" else None
    source = "synthetic" if demo else "razorpay_test"

    return {
        "subscription_id": subscription_id,
        "source": source,
        "enrichment_state": "ready" if provider_context else "not_required",
        "provider_invoice_id": provider_context.invoice_id if provider_context else None,
        "provider_order_id": provider_context.order_id if provider_context else None,
        "customer_name": str(demo.get("customer_name") or f"Test customer {subscription_id[-4:]}")[:120],
        "status": status,
        "failure_reason": canonical_reason,
        "amount_paise": amount,
        "days_overdue": base["days_overdue"],
        "retry_count": provider_context.retry_count if provider_context else base["retry_count"],
        "prior_successes": provider_context.prior_successes if provider_context else base["prior_successes"],
        "previous_interventions": base["previous_interventions"],
        "contacts_7d": base["contacts_7d"],
        "next_retry_at": next_retry,
    }


def case_as_dict(case: SubscriptionCaseModel) -> dict:
    return {
        "id": case.id,
        "subscription_id": case.subscription_id,
        "customer_name": case.customer_name,
        "status": case.status,
        "failure_reason": case.failure_reason,
        "amount_paise": case.amount_paise,
        "amount_rupees": case.amount_paise / 100,
        "days_overdue": case.days_overdue,
        "retry_count": case.retry_count,
        "prior_successes": case.prior_successes,
        "previous_interventions": case.previous_interventions,
        "contacts_7d": case.contacts_7d,
        "next_retry_at": case.next_retry_at,
        "recovered_amount_paise": case.recovered_amount_paise,
        "active_recovery_link_id": case.active_recovery_link_id,
        "active_recovery_link_url": case.active_recovery_link_url,
    }


def _redact_processed_webhook(event: WebhookEventModel) -> None:
    event.payload_json = json_dumps({"event": event.event_type, "redacted": True})


def mark_webhook_enrichment_failed(db: Session, webhook_db_id: str) -> None:
    event = db.get(WebhookEventModel, webhook_db_id)
    if not event or event.event_type not in {"subscription.pending", "subscription.halted", "subscription.charged"}:
        return
    try:
        base = _subscription_event_base(json.loads(event.payload_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    case = db.scalar(
        select(SubscriptionCaseModel).where(
            SubscriptionCaseModel.subscription_id == base["subscription_id"]
        )
    )
    if not case or case.enrichment_state != "pending":
        return
    case.enrichment_state = "failed"
    audit(
        db,
        "enrichment",
        "Invoice enrichment needs attention",
        "Authoritative Razorpay context could not be verified after three attempts. No recovery action was proposed.",
        case_id=case.id,
        severity="error",
    )


def _process_payment_link_paid(db: Session, event: WebhookEventModel, payload: dict) -> None:
    paid = normalize_payment_link_paid(payload)
    case = db.get(SubscriptionCaseModel, paid["case_id"])
    expected_reference = f"pm-{case.id[-20:]}" if case else ""
    mismatch = (
        case is None
        or case.active_recovery_link_id != paid["link_id"]
        or case.amount_paise != paid["amount_paise"]
        or expected_reference != paid["reference_id"]
    )
    if mismatch:
        audit(
            db,
            "safety",
            "Unmatched Payment Link payment blocked",
            "The payment was retained as an event but not attributed to a recovery case.",
            case_id=case.id if case else None,
            severity="warning",
            metadata={"link_id": paid["link_id"], "payment_id": paid["payment_id"]},
        )
    else:
        case.status = "charged"
        case.recovered_amount_paise = paid["amount_paise"]
        case.last_event_created_at = as_utc(event.event_created_at or event.received_at)
        proposal = db.scalar(
            select(RecoveryProposalModel)
            .where(RecoveryProposalModel.case_id == case.id)
            .order_by(RecoveryProposalModel.created_at.desc())
        )
        if proposal:
            proposal.state = "executed"
        audit(
            db,
            "recovery",
            "Revenue recovered by Payment Link",
            f"₹{paid['amount_paise'] / 100:,.2f} matched to the approved recovery link.",
            case_id=case.id,
            metadata={"link_id": paid["link_id"], "payment_id": paid["payment_id"]},
        )

    event.processed_at = utcnow()
    _redact_processed_webhook(event)
    db.commit()


def process_webhook_event(db: Session, webhook_db_id: str, settings: Settings) -> None:
    event = db.get(WebhookEventModel, webhook_db_id)
    if not event or event.processed_at:
        return
    payload = json.loads(event.payload_json)
    if event.event_type == "payment_link.paid":
        _process_payment_link_paid(db, event, payload)
        return
    base = _subscription_event_base(payload)
    case = db.scalar(
        select(SubscriptionCaseModel).where(
            SubscriptionCaseModel.subscription_id == base["subscription_id"]
        )
    )
    state_applied = True
    incoming_created = as_utc(event.event_created_at or event.received_at)

    if base["status"] in {"cancelled", "completed"}:
        if case is None:
            audit(
                db,
                "lifecycle",
                "Terminal subscription retained without a recovery case",
                base["status"],
                metadata={"subscription_id": base["subscription_id"]},
            )
        else:
            last_event_created = as_utc(case.last_event_created_at) if case.last_event_created_at else None
            if last_event_created is None or incoming_created >= last_event_created:
                case.status = base["status"]
                case.last_event_created_at = incoming_created
                existing = db.scalar(
                    select(RecoveryProposalModel)
                    .where(RecoveryProposalModel.case_id == case.id)
                    .order_by(RecoveryProposalModel.created_at.desc())
                )
                if existing and existing.state == "proposed":
                    existing.state = "resolved_terminally"
                audit(db, "lifecycle", "Terminal subscription observed", base["status"], case_id=case.id)
            else:
                audit(
                    db,
                    "safety",
                    "Out-of-order event retained",
                    "Older event was recorded without rolling back case state.",
                    case_id=case.id,
                )
        event.processed_at = utcnow()
        _redact_processed_webhook(event)
        db.commit()
        return

    provider_context: ProviderSubscriptionContext | None = None
    if _embedded_amount(payload) is None:
        if case is None:
            case = SubscriptionCaseModel(
                id=new_id("case"),
                subscription_id=base["subscription_id"],
                source="synthetic" if base["demo"] else "razorpay_test",
                enrichment_state="pending",
                customer_name=str(base["demo"].get("customer_name") or f"Test customer {base['subscription_id'][-4:]}")[:120],
                status=base["status"],
                failure_reason="unknown",
                amount_paise=0,
                days_overdue=base["days_overdue"],
                retry_count=base["retry_count"],
                prior_successes=base["prior_successes"],
                previous_interventions=base["previous_interventions"],
                contacts_7d=base["contacts_7d"],
                last_event_created_at=incoming_created,
            )
            db.add(case)
        else:
            case.enrichment_state = "pending"
        audit(
            db,
            "enrichment",
            "Fetching authoritative invoice context",
            "The webhook was valid but did not contain a recoverable amount.",
            case_id=case.id,
        )
        db.commit()
        provider_context = RazorpayGateway(settings).fetch_subscription_context(
            base["subscription_id"],
            retry_count=base["retry_count"],
            prior_successes=base["prior_successes"],
        )

    normalized = normalize_webhook(payload, provider_context)
    case = db.scalar(
        select(SubscriptionCaseModel).where(
            SubscriptionCaseModel.subscription_id == normalized["subscription_id"]
        )
    )
    if case is None:
        case = SubscriptionCaseModel(id=new_id("case"), last_event_created_at=incoming_created, **normalized)
        db.add(case)
    else:
        if normalized["status"] == "charged" and normalized["amount_paise"] != case.amount_paise:
            audit(
                db,
                "safety",
                "Mismatched subscription charge blocked",
                "A successful subscription event had a different amount and could not close the case.",
                case_id=case.id,
                severity="warning",
            )
            event.processed_at = utcnow()
            _redact_processed_webhook(event)
            db.commit()
            return
        last_event_created = as_utc(case.last_event_created_at) if case.last_event_created_at else None
        if normalized["status"] == "charged" or last_event_created is None or incoming_created >= last_event_created:
            for key, value in normalized.items():
                if key != "subscription_id":
                    if key == "failure_reason" and value == "unknown" and case.failure_reason != "unknown":
                        continue
                    setattr(case, key, value)
            if last_event_created is None or incoming_created > last_event_created:
                case.last_event_created_at = incoming_created
        else:
            state_applied = False
            audit(db, "safety", "Out-of-order event retained", "Older event was recorded without rolling back case state.", case_id=case.id)

    db.flush()
    if not state_applied:
        event.processed_at = utcnow()
        _redact_processed_webhook(event)
        db.commit()
        return

    if normalized["status"] == "charged":
        audit(
            db,
            "lifecycle",
            "Subscription resolved by recurring charge",
            "The subscription recovered through Razorpay's recurring charge, not a PayMender Payment Link.",
            case_id=case.id,
        )
        existing = db.scalar(select(RecoveryProposalModel).where(RecoveryProposalModel.case_id == case.id).order_by(RecoveryProposalModel.created_at.desc()))
        if existing:
            existing.state = "resolved_organically"
    elif normalized["status"] in {"pending", "halted"}:
        create_proposal(db, case, settings)
        if provider_context:
            audit(
                db,
                "enrichment",
                "Invoice context verified",
                f"{provider_context.invoice_id} matched the subscription and INR amount.",
                case_id=case.id,
                metadata={
                    "invoice_id": provider_context.invoice_id,
                    "order_id": provider_context.order_id,
                },
            )

    event.processed_at = utcnow()
    _redact_processed_webhook(event)
    db.commit()


def create_proposal(db: Session, case: SubscriptionCaseModel, settings: Settings) -> RecoveryProposalModel:
    case_data = case_as_dict(case)
    scores = recovery_model.score_actions(case_data)
    advisor = GeminiAdvisor(settings)
    gemini_decision, provider = advisor.propose(case_data, scores)
    policy = decide_policy(case_data, gemini_decision.recommended_action, gemini_decision.confidence, settings)
    chosen_score = next((item for item in scores if item.action == policy.action), scores[0])
    proposal = RecoveryProposalModel(
        id=new_id("prop"),
        case_id=case.id,
        recommended_action=policy.action.value,
        model_recommended_action=gemini_decision.recommended_action.value,
        confidence=gemini_decision.confidence,
        explanation=gemini_decision.explanation,
        evidence_json=json_dumps(gemini_decision.evidence),
        message_english=gemini_decision.message_english,
        message_hinglish=gemini_decision.message_hinglish,
        expected_value_rupees=chosen_score.expected_value_rupees,
        action_scores_json=json_dumps([item.model_dump() for item in scores]),
        requires_approval=policy.requires_approval,
        state="proposed" if policy.requires_approval else "executed",
        policy_reason=policy.reason,
        provider=provider,
    )
    db.add(proposal)
    audit(
        db,
        "proposal",
        "Recovery action proposed" if policy.requires_approval else "Safe action executed",
        f"{policy.action.value}: {policy.reason}",
        case_id=case.id,
        metadata={"provider": provider, "overridden": policy.overridden},
    )
    if policy.overridden:
        audit(db, "safety", "AI proposal overridden", f"Policy changed {gemini_decision.recommended_action.value} to {policy.action.value}.", case_id=case.id, severity="warning")
    return proposal


def approve_proposal(db: Session, case_id: str, decision: str, note: str, settings: Settings) -> RecoveryProposalModel:
    case = db.get(SubscriptionCaseModel, case_id)
    if not case:
        raise LookupError("Case not found")
    proposal = db.scalar(
        select(RecoveryProposalModel)
        .where(
            RecoveryProposalModel.case_id == case_id,
            RecoveryProposalModel.state.in_(["proposed", "retryable_failure"]),
        )
        .order_by(RecoveryProposalModel.created_at.desc())
    )
    if not proposal:
        raise LookupError("No pending proposal exists")
    if decision == "reject":
        proposal.state = "rejected"
        audit(db, "approval", "Proposal rejected", note or "Operator rejected the proposal.", case_id=case_id, severity="warning")
        db.commit()
        return proposal

    policy = decide_policy(case_as_dict(case), RecoveryAction(proposal.recommended_action), proposal.confidence, settings)
    if not policy.allowed or policy.action.value != proposal.recommended_action:
        proposal.state = "blocked"
        audit(db, "safety", "Stale approval blocked", policy.reason, case_id=case_id, severity="warning")
        db.commit()
        raise ValueError(policy.reason)

    proposal.state = "approved"
    action = RecoveryAction(proposal.recommended_action)
    if action == RecoveryAction.CREATE_RECOVERY_LINK:
        real_count = db.scalar(select(func.count()).select_from(ActionExecutionModel).where(ActionExecutionModel.adapter == "razorpay-test")) or 0
        if settings.razorpay_enabled and real_count >= settings.max_real_payment_links:
            proposal.state = "blocked"
            audit(db, "safety", "Sandbox link cap reached", "No additional real test links are permitted.", case_id=case_id, severity="warning")
            db.commit()
            raise ValueError("Sandbox link cap reached")
        execution = db.scalar(
            select(ActionExecutionModel).where(
                ActionExecutionModel.case_id == case.id,
                ActionExecutionModel.action == action.value,
            )
        )
        if execution is None:
            execution = ActionExecutionModel(
                id=new_id("exec"), case_id=case.id, proposal_id=proposal.id, action=action.value, status="executing"
            )
            db.add(execution)
        elif execution.status != "retryable_failure":
            proposal.state = "blocked"
            audit(db, "safety", "Duplicate execution blocked", "An action execution already exists for this case.", case_id=case_id, severity="warning")
            db.commit()
            raise ValueError("An action execution already exists for this case")
        else:
            execution.status = "executing"
            execution.error = None
        execution.adapter = "razorpay-test" if settings.razorpay_enabled else "demo"
        db.flush()
        try:
            result = RazorpayGateway(settings).create_recovery_link(case_as_dict(case))
            execution.status = "completed"
            execution.external_id = result.id
            execution.external_url = result.url
            execution.adapter = result.adapter
            execution.completed_at = utcnow()
            case.active_recovery_link_id = result.id
            case.active_recovery_link_url = result.url
            case.previous_interventions += 1
            case.contacts_7d += 1
            proposal.state = "executed"
            audit(db, "execution", "Recovery link created", f"{result.adapter} created {result.id}; no notification was sent.", case_id=case_id)
        except Exception as exc:
            execution.status = "retryable_failure"
            execution.error = type(exc).__name__
            proposal.state = "retryable_failure"
            audit(db, "failure", "Razorpay action failed safely", "The action is retryable and no duplicate link was recorded.", case_id=case_id, severity="error")
            db.commit()
            raise
    elif action == RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE:
        proposal.state = "executed"
        case.previous_interventions += 1
        audit(db, "approval", "Message preview approved", "Preview finalized; no SMS, email or WhatsApp message was sent.", case_id=case_id)
    db.commit()
    return proposal


def proposal_view(model: RecoveryProposalModel) -> ProposalView:
    raw_scores = json.loads(model.action_scores_json)
    scores = [ActionScore.model_validate(item) for item in raw_scores]
    return ProposalView(
        id=model.id,
        case_id=model.case_id,
        recommended_action=RecoveryAction(model.recommended_action),
        model_recommended_action=RecoveryAction(model.model_recommended_action),
        confidence=model.confidence,
        explanation=model.explanation,
        evidence=json.loads(model.evidence_json),
        message_english=model.message_english,
        message_hinglish=model.message_hinglish,
        expected_value_rupees=model.expected_value_rupees,
        action_scores=scores,
        requires_approval=model.requires_approval,
        state=model.state,
        policy_reason=model.policy_reason,
        provider=model.provider,
        created_at=model.created_at,
    )


def list_cases(db: Session) -> list[CaseSummary]:
    rows = db.scalars(select(SubscriptionCaseModel).order_by(SubscriptionCaseModel.updated_at.desc())).all()
    return [CaseSummary.model_validate(row) for row in rows]


def get_case(db: Session, case_id: str) -> CaseDetail | None:
    row = db.get(SubscriptionCaseModel, case_id)
    if not row:
        return None
    summary = CaseSummary.model_validate(row)
    proposals = [proposal_view(item) for item in sorted(row.proposals, key=lambda p: p.created_at, reverse=True)]
    return CaseDetail(**summary.model_dump(), proposals=proposals)


def list_audit(db: Session, limit: int = 100) -> list[AuditView]:
    rows = db.scalars(select(AuditEventModel).order_by(AuditEventModel.created_at.desc()).limit(limit)).all()
    return [AuditView(
        id=row.id, case_id=row.case_id, category=row.category, title=row.title, detail=row.detail,
        severity=row.severity, metadata=json.loads(row.metadata_json), created_at=row.created_at,
    ) for row in rows]


def metrics(db: Session, settings: Settings) -> MetricsView:
    source = "synthetic" if settings.demo_mode else "razorpay_test"
    cases = db.scalars(
        select(SubscriptionCaseModel).where(SubscriptionCaseModel.source == source)
    ).all()
    case_ids = {item.id for item in cases}
    latest_proposals = [
        item for item in db.scalars(select(RecoveryProposalModel)).all()
        if item.case_id in case_ids
    ]
    predicted = sum(max(item.expected_value_rupees, 0) * 100 for item in latest_proposals if item.state in {"proposed", "approved"})
    blocked = db.scalar(select(func.count()).select_from(AuditEventModel).where(AuditEventModel.category == "safety")) or 0
    return MetricsView(
        display_name=settings.app_display_name,
        demo_mode=settings.demo_mode,
        total_cases=len(cases),
        at_risk_paise=sum(
            item.amount_paise
            for item in cases
            if item.enrichment_state not in {"pending", "failed"}
            and item.status not in {"charged", "cancelled", "completed"}
        ),
        predicted_recoverable_paise=int(predicted),
        recovered_paise=sum(item.recovered_amount_paise for item in cases),
        pending_approvals=sum(1 for item in latest_proposals if item.state == "proposed"),
        stopped_cases=sum(1 for item in latest_proposals if item.recommended_action == RecoveryAction.STOP_CONTACT.value),
        escalated_cases=sum(1 for item in latest_proposals if item.recommended_action == RecoveryAction.ESCALATE_HUMAN.value),
        blocked_actions=blocked,
    )


def save_evaluation(db: Session, settings: Settings) -> EvaluationSummary:
    result = run_evaluation(recovery_model, settings)
    db.add(EvaluationRunModel(id=result.id, label=result.label, summary_json=result.model_dump_json()))
    db.commit()
    return result


def latest_evaluation(db: Session) -> EvaluationSummary | None:
    row = db.scalar(select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc()))
    return EvaluationSummary.model_validate_json(row.summary_json) if row else None


DEMO_CASES = [
    {"name": "Aarav Mehta", "status": "halted", "reason": "expired_card", "amount": 149_900, "days": 6, "retry": 4, "successes": 13, "contacts": 1},
    {"name": "Isha Rao", "status": "pending", "reason": "issuer_downtime", "amount": 49_900, "days": 1, "retry": 1, "successes": 7, "contacts": 0},
    {"name": "Kabir Shah", "status": "halted", "reason": "mandate_cancelled", "amount": 79_900, "days": 9, "retry": 4, "successes": 5, "contacts": 2},
    {"name": "Meera Nair", "status": "pending", "reason": "insufficient_funds", "amount": 29_900, "days": 2, "retry": 2, "successes": 10, "contacts": 1},
    {"name": "Rohan Das", "status": "halted", "reason": "unknown", "amount": 249_900, "days": 12, "retry": 5, "successes": 1, "contacts": 0},
    {"name": "Zoya Khan", "status": "halted", "reason": "bank_blocked", "amount": 9_900, "days": 8, "retry": 4, "successes": 2, "contacts": 1},
    {"name": "Neil Verma", "status": "halted", "reason": "expired_card", "amount": 99_900, "days": 11, "retry": 4, "successes": 9, "contacts": 3},
]


def reset_demo(db: Session, settings: Settings) -> None:
    for table in [ActionExecutionModel, RecoveryProposalModel, JobModel, WebhookEventModel, AuditEventModel, EvaluationRunModel, SubscriptionCaseModel]:
        db.execute(delete(table))
    db.commit()
    now = datetime.now(timezone.utc)
    for index, item in enumerate(DEMO_CASES):
        case = SubscriptionCaseModel(
            id=f"case_demo_{index + 1}", subscription_id=f"sub_demo_{index + 1}", customer_name=item["name"],
            source="synthetic", enrichment_state="not_required",
            status=item["status"], failure_reason=item["reason"], amount_paise=item["amount"],
            days_overdue=item["days"], retry_count=item["retry"], prior_successes=item["successes"],
            previous_interventions=0, contacts_7d=item["contacts"],
            next_retry_at=(now + timedelta(days=1)) if item["status"] == "pending" else None,
            last_event_created_at=now,
        )
        db.add(case)
        db.flush()
        create_proposal(db, case, settings)
    audit(db, "demo", "Demo dataset ready", "Seven synthetic subscription cases were evaluated.")
    db.commit()


def initialize_demo_data(db: Session, settings: Settings) -> None:
    if settings.demo_mode and not list_cases(db):
        reset_demo(db, settings)
