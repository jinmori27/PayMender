from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import JobModel, SubscriptionCaseModel, WebhookEventModel
from app.worker import claim_and_process_one


def test_expired_worker_lease_is_reclaimed_and_completed(db):
    payload = {
        "event": "subscription.pending",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_worker_reclaim",
                    "status": "pending",
                    "remaining_count": 1,
                    "notes": {"failure_reason": "issuer downtime", "amount_paise": 49_900},
                }
            }
        },
    }
    event = WebhookEventModel(
        id="webhook_worker_reclaim",
        event_id="evt_worker_reclaim",
        event_type="subscription.pending",
        payload_json=json.dumps(payload),
        event_created_at=datetime.now(timezone.utc),
    )
    job = JobModel(
        id="job_worker_reclaim",
        kind="process_webhook",
        payload_json=json.dumps({"webhook_event_id": event.id}),
        status="running",
        attempts=1,
        lease_until=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add_all([event, job])
    db.commit()

    assert claim_and_process_one(get_settings())

    with SessionLocal() as session:
        recovered_job = session.get(JobModel, job.id)
        case = session.scalar(select(SubscriptionCaseModel).where(SubscriptionCaseModel.subscription_id == "sub_worker_reclaim"))
        assert recovered_job.status == "completed"
        assert recovered_job.attempts == 2
        assert recovered_job.lease_until is None
        assert case is not None
        assert case.status == "pending"


def test_permanently_failed_webhook_job_redacts_raw_payload(db):
    event = WebhookEventModel(
        id="webhook_worker_failed",
        event_id="evt_worker_failed",
        event_type="subscription.pending",
        payload_json=json.dumps({"event": "subscription.pending", "customer_email": "erase-me@example.test"}),
        event_created_at=datetime.now(timezone.utc),
    )
    job = JobModel(
        id="job_worker_failed",
        kind="process_webhook",
        payload_json=json.dumps({"webhook_event_id": event.id}),
        status="pending",
        attempts=2,
    )
    db.add_all([event, job])
    db.commit()

    assert claim_and_process_one(get_settings())

    with SessionLocal() as session:
        failed_job = session.get(JobModel, job.id)
        redacted_event = session.get(WebhookEventModel, event.id)
        assert failed_job.status == "failed"
        assert "erase-me" not in redacted_event.payload_json


def test_enrichment_exhaustion_marks_case_failed_without_money_action(db, monkeypatch):
    provider_payload = {
        "event": "subscription.halted",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_enrichment_exhausted_123",
                    "status": "halted",
                    "auth_attempts": 4,
                    "paid_count": 3,
                }
            }
        },
    }
    event = WebhookEventModel(
        id="webhook_enrichment_exhausted",
        event_id="evt_enrichment_exhausted",
        event_type="subscription.halted",
        payload_json=json.dumps(provider_payload),
        event_created_at=datetime.now(timezone.utc),
    )
    job = JobModel(
        id="job_enrichment_exhausted",
        kind="process_webhook",
        payload_json=json.dumps({"webhook_event_id": event.id}),
        status="pending",
        attempts=2,
    )
    db.add_all([event, job])
    db.commit()
    monkeypatch.setattr(
        "app.services.RazorpayGateway.fetch_subscription_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    assert claim_and_process_one(get_settings())

    with SessionLocal() as session:
        failed_job = session.get(JobModel, job.id)
        case = session.scalar(
            select(SubscriptionCaseModel).where(
                SubscriptionCaseModel.subscription_id == "sub_enrichment_exhausted_123"
            )
        )
        assert failed_job.status == "failed"
        assert case is not None
        assert case.enrichment_state == "failed"
        assert case.amount_paise == 0
        assert case.proposals == []
