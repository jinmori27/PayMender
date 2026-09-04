from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import ActionExecutionModel, RecoveryProposalModel, SubscriptionCaseModel
from app.razorpay import PaymentLinkResult, RazorpayGateway
from app.services import approve_proposal


def test_link_requires_approval_and_executes_once(db):
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    proposal = db.scalar(select(RecoveryProposalModel).where(RecoveryProposalModel.case_id == case.id).order_by(RecoveryProposalModel.created_at.desc()))
    assert proposal is not None
    assert proposal.recommended_action == "CREATE_RECOVERY_LINK"
    assert proposal.state == "proposed"

    approve_proposal(db, case.id, "approve", "test approval", get_settings())
    db.refresh(case)
    assert case.active_recovery_link_id is not None
    assert case.active_recovery_link_id.startswith("plink_demo_")
    count = db.scalar(select(func.count()).select_from(ActionExecutionModel).where(ActionExecutionModel.case_id == case.id))
    assert count == 1

    with pytest.raises(LookupError):
        approve_proposal(db, case.id, "approve", "duplicate", get_settings())
    count_after = db.scalar(select(func.count()).select_from(ActionExecutionModel).where(ActionExecutionModel.case_id == case.id))
    assert count_after == 1


def test_contact_capped_demo_case_is_stopped(db):
    proposal = db.scalar(select(RecoveryProposalModel).where(RecoveryProposalModel.case_id == "case_demo_7"))
    assert proposal is not None
    assert proposal.recommended_action == "STOP_CONTACT"
    assert proposal.state == "executed"


def test_razorpay_failure_retries_without_duplicate_execution(db, monkeypatch):
    case = db.get(SubscriptionCaseModel, "case_demo_1")

    def fail_once(_gateway, _case):
        raise RuntimeError("simulated upstream 500")

    monkeypatch.setattr(RazorpayGateway, "create_recovery_link", fail_once)
    with pytest.raises(RuntimeError):
        approve_proposal(db, case.id, "approve", "first attempt", get_settings())

    proposal = db.scalar(select(RecoveryProposalModel).where(RecoveryProposalModel.case_id == case.id))
    execution = db.scalar(select(ActionExecutionModel).where(ActionExecutionModel.case_id == case.id))
    assert proposal.state == "retryable_failure"
    assert execution.status == "retryable_failure"
    assert case.active_recovery_link_id is None

    monkeypatch.setattr(
        RazorpayGateway,
        "create_recovery_link",
        lambda _gateway, _case: PaymentLinkResult("plink_retry_success", "https://example.invalid/retry", "demo"),
    )
    approve_proposal(db, case.id, "approve", "retry", get_settings())
    db.refresh(execution)
    db.refresh(case)

    count = db.scalar(select(func.count()).select_from(ActionExecutionModel).where(ActionExecutionModel.case_id == case.id))
    assert count == 1
    assert execution.status == "completed"
    assert case.active_recovery_link_id == "plink_retry_success"


def test_real_attempt_is_counted_even_when_upstream_result_is_ambiguous(db, monkeypatch):
    case = db.get(SubscriptionCaseModel, "case_demo_1")
    case.source = "razorpay_test"
    db.commit()
    settings = get_settings().model_copy(update={
        "demo_mode": False,
        "razorpay_key_id": "rzp_test_example",
        "razorpay_key_secret": "secret",
    })

    monkeypatch.setattr(RazorpayGateway, "create_recovery_link", lambda _gateway, _case: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(TimeoutError):
        approve_proposal(db, case.id, "approve", "ambiguous attempt", settings)

    execution = db.scalar(select(ActionExecutionModel).where(ActionExecutionModel.case_id == case.id))
    assert execution.adapter == "razorpay-test"
