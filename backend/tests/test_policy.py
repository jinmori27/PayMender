from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.policy import decide_policy
from app.schemas import RecoveryAction


def base_case(**overrides):
    case = {
        "status": "halted",
        "failure_reason": "expired_card",
        "amount_paise": 99_900,
        "contacts_7d": 1,
        "recovered_amount_paise": 0,
        "active_recovery_link_id": None,
        "next_retry_at": None,
    }
    case.update(overrides)
    return case


def test_recovery_link_is_approval_gated():
    decision = decide_policy(base_case(), RecoveryAction.CREATE_RECOVERY_LINK, 0.9, get_settings())
    assert decision.allowed is True
    assert decision.requires_approval is True
    assert decision.action == RecoveryAction.CREATE_RECOVERY_LINK


def test_pending_retry_suppresses_duplicate_link():
    decision = decide_policy(
        base_case(status="pending", next_retry_at=datetime.now(timezone.utc) + timedelta(hours=2)),
        RecoveryAction.CREATE_RECOVERY_LINK,
        0.9,
        get_settings(),
    )
    assert decision.action == RecoveryAction.WAIT_FOR_RETRY
    assert decision.overridden is True


def test_contact_cap_stops_customer_contact():
    decision = decide_policy(base_case(contacts_7d=3), RecoveryAction.CREATE_RECOVERY_LINK, 0.9, get_settings())
    assert decision.action == RecoveryAction.STOP_CONTACT
    assert decision.requires_approval is False


def test_terminal_case_stops_even_with_high_confidence():
    decision = decide_policy(base_case(status="charged", recovered_amount_paise=99_900), RecoveryAction.CREATE_RECOVERY_LINK, 0.99, get_settings())
    assert decision.action == RecoveryAction.STOP_CONTACT


def test_unknown_low_confidence_escalates():
    decision = decide_policy(base_case(failure_reason="unknown"), RecoveryAction.WAIT_FOR_RETRY, 0.4, get_settings())
    assert decision.action == RecoveryAction.ESCALATE_HUMAN
