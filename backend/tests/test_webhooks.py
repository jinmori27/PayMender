from __future__ import annotations

import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import AuditEventModel, JobModel, SubscriptionCaseModel, WebhookEventModel
from app.razorpay import ProviderSubscriptionContext
from app.services import accept_webhook, normalize_webhook, process_webhook_event, verify_webhook


def signed(body: bytes) -> str:
    return hmac.new(b"test_webhook_secret", body, hashlib.sha256).hexdigest()


def payload(event: str = "subscription.halted") -> bytes:
    return json.dumps({
        "event": event,
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "payload": {"subscription": {"entity": {"id": "sub_test_1", "status": "halted", "paid_count": 4, "notes": {"failure_reason": "expired card", "amount_paise": 99900}}}},
    }).encode()


def test_signature_uses_untouched_raw_body():
    body = payload()
    assert verify_webhook(body, signed(body), "test_webhook_secret")
    assert not verify_webhook(body + b" ", signed(body), "test_webhook_secret")


def test_normalizes_subscription_lifecycle():
    body = json.loads(payload())
    normalized = normalize_webhook(body)
    assert normalized["subscription_id"] == "sub_test_1"
    assert normalized["status"] == "halted"
    assert normalized["failure_reason"] == "expired_card"
    assert normalized["amount_paise"] == 99_900


def test_accepts_official_subscription_only_halted_payload(db):
    body = json.dumps({
        "entity": "event",
        "event": "subscription.halted",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "contains": ["subscription"],
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_official_minimal_123",
                    "entity": "subscription",
                    "status": "halted",
                    "auth_attempts": 4,
                    "paid_count": 6,
                    "notes": {"internal": "no amount is provided here"},
                }
            }
        },
    }).encode()

    duplicate, event_id = accept_webhook(
        db,
        raw_body=body,
        signature=signed(body),
        event_id="evt_official_minimal_halted",
        settings=get_settings(),
    )

    assert duplicate is False
    assert event_id
    assert db.scalar(select(JobModel).where(JobModel.payload_json.contains(event_id))) is not None


def test_worker_enriches_subscription_only_halted_event(db, monkeypatch):
    minimal = {
        "entity": "event",
        "event": "subscription.halted",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_worker_enrichment_123",
                    "status": "halted",
                    "auth_attempts": 4,
                    "paid_count": 8,
                }
            }
        },
    }
    event = WebhookEventModel(
        id="webhook_worker_enrichment",
        event_id="evt_worker_enrichment",
        event_type="subscription.halted",
        payload_json=json.dumps(minimal),
        event_created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    monkeypatch.setattr(
        "app.services.RazorpayGateway.fetch_subscription_context",
        lambda *_args, **_kwargs: ProviderSubscriptionContext(
            subscription_id="sub_worker_enrichment_123",
            invoice_id="inv_worker_enrichment",
            order_id="order_worker_enrichment",
            amount_paise=129_900,
            currency="INR",
            failure_reason="expired_card",
            retry_count=4,
            prior_successes=8,
        ),
    )

    process_webhook_event(db, event.id, get_settings())

    case = db.scalar(
        select(SubscriptionCaseModel).where(
            SubscriptionCaseModel.subscription_id == "sub_worker_enrichment_123"
        )
    )
    assert case is not None
    assert case.source == "razorpay_test"
    assert case.enrichment_state == "ready"
    assert case.provider_invoice_id == "inv_worker_enrichment"
    assert case.provider_order_id == "order_worker_enrichment"
    assert case.amount_paise == 129_900
    assert case.failure_reason == "expired_card"


def test_retry_count_uses_auth_attempts_not_remaining_billing_cycles():
    body = json.loads(payload())
    entity = body["payload"]["subscription"]["entity"]
    entity["auth_attempts"] = 2
    entity["remaining_count"] = 42

    normalized = normalize_webhook(body)

    assert normalized["retry_count"] == 2


def test_unsupported_event_is_rejected_before_storage(db):
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()

    with pytest.raises(ValueError, match="Unsupported Razorpay event"):
        accept_webhook(
            db,
            raw_body=body,
            signature=signed(body),
            event_id="evt_unsupported",
            settings=get_settings(),
        )


def test_missing_subscription_identity_is_rejected(db):
    body = json.dumps({
        "event": "subscription.halted",
        "payload": {"subscription": {"entity": {"status": "halted"}}},
    }).encode()

    with pytest.raises(ValueError, match="subscription id"):
        accept_webhook(
            db,
            raw_body=body,
            signature=signed(body),
            event_id="evt_missing_subscription",
            settings=get_settings(),
        )


def test_malformed_payload_envelope_is_rejected_without_server_error(db):
    body = json.dumps({"event": "subscription.halted", "payload": "not-an-object"}).encode()

    with pytest.raises(ValueError, match="subscription id"):
        accept_webhook(
            db,
            raw_body=body,
            signature=signed(body),
            event_id="evt_malformed_envelope",
            settings=get_settings(),
        )


def test_unbounded_event_identifier_is_rejected(db):
    body = payload()

    with pytest.raises(ValueError, match="event id"):
        accept_webhook(
            db,
            raw_body=body,
            signature=signed(body),
            event_id="e" * 121,
            settings=get_settings(),
        )


def test_ten_concurrent_duplicates_create_one_event(db):
    body = payload()

    def submit(_: int) -> bool:
        with SessionLocal() as session:
            duplicate, _ = accept_webhook(
                session,
                raw_body=body,
                signature=signed(body),
                event_id="evt_concurrent_1",
                settings=get_settings(),
            )
            return duplicate

    with ThreadPoolExecutor(max_workers=10) as pool:
        duplicates = list(pool.map(submit, range(10)))
    with SessionLocal() as session:
        count = session.scalar(select(func.count()).select_from(WebhookEventModel).where(WebhookEventModel.event_id == "evt_concurrent_1"))
        queued = session.scalar(select(func.count()).select_from(JobModel).where(JobModel.kind == "process_webhook"))
    assert count == 1
    assert queued == 1
    assert duplicates.count(False) == 1
    assert duplicates.count(True) == 9


def test_out_of_order_failure_does_not_roll_back_case(db):
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    old_payload = json.loads(payload("subscription.pending"))
    old_payload["payload"]["subscription"]["entity"]["id"] = case.subscription_id
    old_payload["payload"]["subscription"]["entity"]["status"] = "pending"
    event = WebhookEventModel(
        id="webhook_out_of_order",
        event_id="evt_out_of_order",
        event_type="subscription.pending",
        payload_json=json.dumps(old_payload),
        event_created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(event)
    db.commit()

    process_webhook_event(db, event.id, get_settings())
    db.refresh(case)
    db.refresh(event)

    assert case.status == "halted"
    assert event.processed_at is not None
    retained = db.scalar(select(AuditEventModel).where(AuditEventModel.title == "Out-of-order event retained"))
    assert retained is not None


def test_newer_provider_event_is_not_dropped_because_processing_was_delayed(db):
    first_created = datetime.now(timezone.utc) - timedelta(minutes=10)
    first_payload = json.loads(payload("subscription.pending"))
    first_entity = first_payload["payload"]["subscription"]["entity"]
    first_entity["id"] = "sub_delayed_ordering"
    first_entity["status"] = "pending"
    first = WebhookEventModel(
        id="webhook_delayed_first",
        event_id="evt_delayed_first",
        event_type="subscription.pending",
        payload_json=json.dumps(first_payload),
        event_created_at=first_created,
    )
    db.add(first)
    db.commit()
    process_webhook_event(db, first.id, get_settings())

    second_created = first_created + timedelta(minutes=1)
    second_payload = json.loads(payload("subscription.halted"))
    second_entity = second_payload["payload"]["subscription"]["entity"]
    second_entity["id"] = "sub_delayed_ordering"
    second_entity["status"] = "halted"
    second = WebhookEventModel(
        id="webhook_delayed_second",
        event_id="evt_delayed_second",
        event_type="subscription.halted",
        payload_json=json.dumps(second_payload),
        event_created_at=second_created,
    )
    db.add(second)
    db.commit()

    process_webhook_event(db, second.id, get_settings())

    case = db.scalar(select(SubscriptionCaseModel).where(SubscriptionCaseModel.subscription_id == "sub_delayed_ordering"))
    assert case.status == "halted"


def test_charged_event_closes_case_even_when_delivered_late(db):
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    charged_payload = json.loads(payload("subscription.charged"))
    entity = charged_payload["payload"]["subscription"]["entity"]
    entity["id"] = case.subscription_id
    entity["status"] = "charged"
    entity["notes"]["amount_paise"] = case.amount_paise
    event = WebhookEventModel(
        id="webhook_late_success",
        event_id="evt_late_success",
        event_type="subscription.charged",
        payload_json=json.dumps(charged_payload),
        event_created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(event)
    db.commit()

    process_webhook_event(db, event.id, get_settings())
    db.refresh(case)

    assert case.status == "charged"
    assert case.recovered_amount_paise == 0


def test_mismatched_subscription_charge_does_not_close_or_revalue_case(db):
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    original_amount = case.amount_paise
    charged_payload = json.loads(payload("subscription.charged"))
    entity = charged_payload["payload"]["subscription"]["entity"]
    entity["id"] = case.subscription_id
    entity["notes"]["amount_paise"] = 1
    charged_payload["payload"]["payment"] = {"entity": {"amount": 1}}
    event = WebhookEventModel(
        id="webhook_mismatched_charge",
        event_id="evt_mismatched_charge",
        event_type="subscription.charged",
        payload_json=json.dumps(charged_payload),
        event_created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    process_webhook_event(db, event.id, get_settings())
    db.refresh(case)

    assert case.status == "halted"
    assert case.amount_paise == original_amount
    assert case.recovered_amount_paise == 0


def test_verified_payment_link_paid_event_records_paymender_recovery(db):
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    case.active_recovery_link_id = "plink_verified_recovery"
    case.active_recovery_link_url = "https://example.invalid/verified"
    db.commit()
    paid_payload = {
        "event": "payment_link.paid",
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "payload": {
            "payment_link": {
                "entity": {
                    "id": case.active_recovery_link_id,
                    "status": "paid",
                    "amount": case.amount_paise,
                    "amount_paid": case.amount_paise,
                    "currency": "INR",
                    "reference_id": f"pm-{case.id[-20:]}",
                    "notes": {"paymender_case_id": case.id},
                    "customer": {"email": "must-not-be-retained@example.test"},
                }
            },
            "payment": {"entity": {"id": "pay_verified", "amount": case.amount_paise, "status": "captured"}},
        },
    }
    event = WebhookEventModel(
        id="webhook_verified_link_paid",
        event_id="evt_verified_link_paid",
        event_type="payment_link.paid",
        payload_json=json.dumps(paid_payload),
        event_created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    process_webhook_event(db, event.id, get_settings())
    db.refresh(case)
    db.refresh(event)

    assert case.status == "charged"
    assert case.recovered_amount_paise == case.amount_paise
    assert "must-not-be-retained" not in event.payload_json
