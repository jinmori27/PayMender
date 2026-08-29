from __future__ import annotations

from app.config import get_settings
from app.models import SubscriptionCaseModel
from app.services import initialize_demo_data, metrics


def test_demo_initialization_is_disabled_in_razorpay_test_mode(monkeypatch):
    reset_calls: list[bool] = []
    monkeypatch.setattr("app.services.list_cases", lambda _db: [])
    monkeypatch.setattr("app.services.reset_demo", lambda _db, _settings: reset_calls.append(True))
    settings = get_settings().model_copy(update={"demo_mode": False})

    initialize_demo_data(object(), settings)  # type: ignore[arg-type]

    assert reset_calls == []


def test_metrics_never_mix_synthetic_and_razorpay_test_cases(db):
    db.add(SubscriptionCaseModel(
        id="case_real_metrics",
        subscription_id="sub_real_metrics_123",
        source="razorpay_test",
        enrichment_state="ready",
        customer_name="Test customer",
        status="halted",
        failure_reason="expired_card",
        amount_paise=88_800,
        retry_count=4,
    ))
    db.commit()

    demo_metrics = metrics(db, get_settings().model_copy(update={"demo_mode": True}))
    real_metrics = metrics(db, get_settings().model_copy(update={"demo_mode": False}))

    assert demo_metrics.total_cases == 7
    assert real_metrics.total_cases == 1
    assert real_metrics.at_risk_paise == 88_800
