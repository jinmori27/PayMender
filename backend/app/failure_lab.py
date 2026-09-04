from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .gemini import GeminiAdvisor
from .ml import recovery_model
from .models import ActionExecutionModel, JobModel, SubscriptionCaseModel, WebhookEventModel, new_id
from .schemas import FailureScenarioResult
from .services import accept_webhook, approve_proposal, audit, case_as_dict, create_proposal, json_dumps
from .worker import claim_job


def _record_result(
    db: Session,
    scenario: str,
    title: str,
    assertions: dict[str, bool],
    evidence_ids: list[str],
    *,
    severity: str = "warning",
) -> FailureScenarioResult:
    if not assertions or not all(assertions.values()):
        raise RuntimeError(f"Contained scenario failed its assertions: {scenario}")
    record = audit(
        db,
        "safety" if scenario == "duplicate" else "failure",
        title,
        "A deterministic, network-isolated scenario exercised the real containment path.",
        severity=severity,
        metadata={"injected": True, "scenario": scenario, "assertions": assertions},
    )
    db.commit()
    return FailureScenarioResult(
        scenario=scenario,
        status="contained",
        assertions=assertions,
        evidence_ids=[*evidence_ids, record.id],
    )


def _duplicate_scenario(db: Session, settings: Settings) -> FailureScenarioResult:
    marker = uuid4().hex
    event_id = f"evt_lab_duplicate_{marker}"
    payload = {
        "event": "subscription.halted",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "payload": {"subscription": {"entity": {
            "id": f"sub_lab_duplicate_{marker}",
            "status": "halted",
            "auth_attempts": 4,
            "paid_count": 2,
        }}},
        "demo": {
            "amount_paise": 49_900,
            "failure_reason": "expired_card",
            "customer_name": "Contained duplicate fixture",
        },
    }
    raw = json_dumps(payload).encode()
    signature = hmac.new(settings.razorpay_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    results = [
        accept_webhook(
            db,
            raw_body=raw,
            signature=signature,
            event_id=event_id,
            settings=settings,
        )
        for _ in range(10)
    ]
    stored = db.scalar(
        select(func.count()).select_from(WebhookEventModel).where(WebhookEventModel.event_id == event_id)
    ) or 0
    accepted_id = next(webhook_id for duplicate, webhook_id in results if not duplicate)
    queued = db.scalar(
        select(func.count()).select_from(JobModel).where(JobModel.payload_json.contains(accepted_id))
    ) or 0
    return _record_result(
        db,
        "duplicate",
        "Duplicate webhook suppression executed",
        {
            "one_event_stored": stored == 1,
            "one_job_queued": queued == 1,
            "nine_duplicates_suppressed": sum(duplicate for duplicate, _ in results) == 9,
        },
        [accepted_id, event_id],
    )


def _gemini_scenario(db: Session, settings: Settings) -> FailureScenarioResult:
    marker = uuid4().hex
    case = SubscriptionCaseModel(
        id=f"case_lab_gemini_{marker}",
        subscription_id=f"sub_lab_gemini_{marker}",
        source="synthetic",
        enrichment_state="not_required",
        customer_name="Contained Gemini fixture",
        status="halted",
        failure_reason="expired_card",
        amount_paise=99_900,
        days_overdue=7,
        retry_count=4,
        prior_successes=8,
        previous_interventions=0,
        contacts_7d=0,
        recovered_amount_paise=0,
        active_recovery_link_id=None,
        active_recovery_link_url=None,
        last_event_created_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.flush()
    scores = recovery_model.score_actions(case_as_dict(case))
    executions_before = db.scalar(select(func.count()).select_from(ActionExecutionModel)) or 0

    def unavailable_client(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("contained Gemini quota failure")

    configured = settings.model_copy(update={"gemini_api_key": "contained-test-key"})
    decision, provider = GeminiAdvisor(configured, client_factory=unavailable_client).propose(
        case_as_dict(case),
        scores,
    )
    executions_after = db.scalar(select(func.count()).select_from(ActionExecutionModel)) or 0
    return _record_result(
        db,
        "gemini-quota",
        "Gemini failure fallback executed",
        {
            "deterministic_fallback_used": provider.startswith("deterministic-fallback:"),
            "safe_action_preserved": decision.recommended_action == scores[0].action,
            "no_action_executed": executions_before == executions_after,
        },
        [case.id],
    )


class _FailingGateway:
    def create_recovery_link(self, _case: dict):  # type: ignore[no-untyped-def]
        raise RuntimeError("contained Razorpay 500")


def _razorpay_scenario(db: Session, settings: Settings) -> FailureScenarioResult:
    marker = uuid4().hex
    case = SubscriptionCaseModel(
        id=f"case_lab_{marker}",
        subscription_id=f"sub_lab_{marker}",
        source="synthetic",
        enrichment_state="not_required",
        customer_name="Contained Razorpay fixture",
        status="halted",
        failure_reason="expired_card",
        amount_paise=99_900,
        days_overdue=7,
        retry_count=4,
        prior_successes=8,
        previous_interventions=0,
        contacts_7d=0,
        recovered_amount_paise=0,
        active_recovery_link_id=None,
        active_recovery_link_url=None,
        last_event_created_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.flush()
    proposal = create_proposal(db, case, settings)
    db.commit()
    if proposal.recommended_action != "CREATE_RECOVERY_LINK":
        raise RuntimeError("Contained fixture did not produce a recovery-link proposal")
    try:
        approve_proposal(
            db,
            case.id,
            "approve",
            "Contained Reliability Lab approval",
            settings,
            gateway_factory=lambda _settings: _FailingGateway(),  # type: ignore[arg-type,return-value]
        )
    except RuntimeError:
        pass
    execution = db.scalar(
        select(ActionExecutionModel).where(ActionExecutionModel.case_id == case.id)
    )
    return _record_result(
        db,
        "razorpay-500",
        "Razorpay failure containment executed",
        {
            "execution_is_retryable": bool(execution and execution.status == "retryable_failure"),
            "no_external_id_recorded": bool(execution and execution.external_id is None),
            "no_recovery_link_stored": case.active_recovery_link_id is None,
        },
        [case.id, proposal.id, execution.id if execution else "missing-execution"],
        severity="error",
    )


def _worker_scenario(db: Session, settings: Settings) -> FailureScenarioResult:
    job = JobModel(
        id=new_id("job"),
        kind="contained-test",
        payload_json="{}",
        status="running",
        attempts=1,
        lease_until=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db.add(job)
    db.commit()
    claimed = claim_job(db, job.id, settings)
    if claimed:
        claimed.status = "completed"
        claimed.lease_until = None
        db.commit()
    return _record_result(
        db,
        "worker-crash",
        "Expired worker lease recovery executed",
        {
            "expired_lease_reclaimed": claimed is not None,
            "attempt_incremented_once": bool(claimed and claimed.attempts == 2),
            "job_completed": bool(claimed and claimed.status == "completed"),
        },
        [job.id],
    )


def execute_failure_scenario(
    db: Session,
    scenario: str,
    settings: Settings,
) -> FailureScenarioResult:
    handlers = {
        "duplicate": _duplicate_scenario,
        "gemini-quota": _gemini_scenario,
        "razorpay-500": _razorpay_scenario,
        "worker-crash": _worker_scenario,
    }
    handler = handlers.get(scenario)
    if handler is None:
        raise LookupError("Unknown failure scenario")
    return handler(db, settings)
