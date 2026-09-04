from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import RecoveryProposalModel, SubscriptionCaseModel
from app.services import (
    approve_proposal,
    audit,
    create_proposal,
    get_case,
    initialize_demo_data,
    list_audit,
    list_cases,
    metrics,
)


def test_demo_initialization_is_disabled_in_razorpay_test_mode(monkeypatch):
    reset_calls: list[bool] = []
    monkeypatch.setattr("app.services.list_cases", lambda _db, _settings: [])
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


def test_case_queries_and_approvals_never_cross_modes(db):
    real_case = SubscriptionCaseModel(
        id="case_real_isolation",
        subscription_id="sub_real_isolation_123",
        source="razorpay_test",
        enrichment_state="ready",
        customer_name="Razorpay test subscription",
        status="halted",
        failure_reason="expired_card",
        amount_paise=72_500,
        retry_count=4,
    )
    db.add(real_case)
    db.commit()

    demo_settings = get_settings().model_copy(update={"demo_mode": True})
    real_settings = get_settings().model_copy(update={"demo_mode": False})

    assert {item.source for item in list_cases(db, demo_settings)} == {"synthetic"}
    assert [item.id for item in list_cases(db, real_settings)] == [real_case.id]
    assert get_case(db, real_case.id, demo_settings) is None
    assert get_case(db, "case_demo_1", real_settings) is None

    audit(db, "safety", "Real-mode block", "A real test action was contained.", case_id=real_case.id)
    db.commit()
    assert all(item.title != "Real-mode block" for item in list_audit(db, demo_settings))
    assert all(item.title != "Demo dataset ready" for item in list_audit(db, real_settings))
    assert any(item.title == "Real-mode block" for item in list_audit(db, real_settings))

    with pytest.raises(LookupError, match="Case not found"):
        approve_proposal(db, "case_demo_1", "approve", "", real_settings)


def test_repeated_proposals_supersede_the_previous_action_and_do_not_inflate_metrics(db):
    settings = get_settings()
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    original = db.scalar(
        select(RecoveryProposalModel)
        .where(RecoveryProposalModel.case_id == case.id)
        .order_by(RecoveryProposalModel.created_at.desc())
    )
    before = metrics(db, settings)

    replacement = create_proposal(db, case, settings)
    db.commit()
    db.refresh(original)

    after = metrics(db, settings)
    assert original.state == "superseded"
    assert replacement.state == "proposed"
    assert after.pending_approvals == before.pending_approvals
    assert after.predicted_recoverable_paise == before.predicted_recoverable_paise
