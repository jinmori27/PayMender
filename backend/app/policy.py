from __future__ import annotations

from datetime import datetime, timezone

from .config import Settings
from .schemas import PolicyDecision, RecoveryAction


TERMINAL_STATUSES = {"charged", "cancelled", "completed"}


def decide_policy(
    case: dict,
    proposed_action: RecoveryAction,
    confidence: float,
    settings: Settings,
) -> PolicyDecision:
    status = case["status"]
    if status in TERMINAL_STATUSES or case.get("recovered_amount_paise", 0) > 0:
        return PolicyDecision(
            action=RecoveryAction.STOP_CONTACT,
            allowed=True,
            requires_approval=False,
            overridden=proposed_action != RecoveryAction.STOP_CONTACT,
            reason="Subscription is terminal or already recovered; further contact is stopped.",
        )

    if case["contacts_7d"] >= settings.contact_cap_7d:
        return PolicyDecision(
            action=RecoveryAction.STOP_CONTACT,
            allowed=True,
            requires_approval=False,
            overridden=proposed_action != RecoveryAction.STOP_CONTACT,
            reason=f"Seven-day contact cap of {settings.contact_cap_7d} has been reached.",
        )

    if case["amount_paise"] < settings.min_recovery_amount_paise:
        return PolicyDecision(
            action=RecoveryAction.STOP_CONTACT,
            allowed=True,
            requires_approval=False,
            overridden=proposed_action != RecoveryAction.STOP_CONTACT,
            reason="Outstanding amount is below the configured recovery floor.",
        )

    if case["failure_reason"] == "unknown" and confidence < 0.60:
        return PolicyDecision(
            action=RecoveryAction.ESCALATE_HUMAN,
            allowed=True,
            requires_approval=False,
            overridden=proposed_action != RecoveryAction.ESCALATE_HUMAN,
            reason="Unknown failure with low confidence is escalated instead of guessed.",
        )

    retry_at = case.get("next_retry_at")
    if status == "pending" and retry_at:
        if isinstance(retry_at, str):
            retry_at = datetime.fromisoformat(retry_at.replace("Z", "+00:00"))
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        if retry_at > datetime.now(timezone.utc):
            return PolicyDecision(
                action=RecoveryAction.WAIT_FOR_RETRY,
                allowed=True,
                requires_approval=False,
                overridden=proposed_action != RecoveryAction.WAIT_FOR_RETRY,
                reason="Razorpay has another retry scheduled; duplicate recovery is suppressed.",
            )

    if proposed_action == RecoveryAction.CREATE_RECOVERY_LINK:
        if status != "halted":
            return PolicyDecision(
                action=RecoveryAction.WAIT_FOR_RETRY if status == "pending" else RecoveryAction.ESCALATE_HUMAN,
                allowed=True,
                requires_approval=False,
                overridden=True,
                reason="Recovery links are restricted to halted subscriptions.",
            )
        if case.get("active_recovery_link_id"):
            return PolicyDecision(
                action=RecoveryAction.STOP_CONTACT,
                allowed=True,
                requires_approval=False,
                overridden=True,
                reason="An active recovery link already exists; a duplicate is blocked.",
            )
        return PolicyDecision(
            action=proposed_action,
            allowed=True,
            requires_approval=True,
            reason="Halted subscription is eligible, but link creation requires operator approval.",
        )

    if proposed_action == RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE:
        return PolicyDecision(
            action=proposed_action,
            allowed=True,
            requires_approval=True,
            reason="Customer outreach remains a preview until an operator approves it.",
        )

    return PolicyDecision(
        action=proposed_action,
        allowed=True,
        requires_approval=False,
        reason="Action is internal, bounded and does not move money or contact a customer.",
    )
