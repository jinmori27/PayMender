from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from random import Random

from .schemas import FailureReason, RecoveryAction


FAILURE_REASONS = [reason.value for reason in FailureReason]
ACTIONS = [action.value for action in RecoveryAction]


@dataclass(slots=True)
class SyntheticRecord:
    case_id: str
    status: str
    failure_reason: str
    amount_rupees: float
    days_overdue: int
    retry_count: int
    prior_successes: int
    previous_interventions: int
    contacts_7d: int
    action: str
    recovered: int


def ground_truth_probability(case: dict, action: str) -> float:
    base = {
        RecoveryAction.WAIT_FOR_RETRY.value: 0.40,
        RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE.value: 0.52,
        RecoveryAction.CREATE_RECOVERY_LINK.value: 0.62,
        RecoveryAction.ESCALATE_HUMAN.value: 0.24,
        RecoveryAction.STOP_CONTACT.value: 0.0,
    }[action]

    reason = case["failure_reason"]
    status = case["status"]
    if reason == FailureReason.ISSUER_DOWNTIME.value:
        base += 0.38 if action == RecoveryAction.WAIT_FOR_RETRY.value else -0.18
    elif reason == FailureReason.INSUFFICIENT_FUNDS.value:
        base += 0.17 if action == RecoveryAction.WAIT_FOR_RETRY.value and case["days_overdue"] < 4 else 0.03
    elif reason == FailureReason.EXPIRED_CARD.value:
        if action == RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE.value:
            base += 0.32
        elif action == RecoveryAction.CREATE_RECOVERY_LINK.value:
            base += 0.14
        elif action == RecoveryAction.WAIT_FOR_RETRY.value:
            base -= 0.28
    elif reason == FailureReason.BANK_BLOCKED.value:
        if action in {RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE.value, RecoveryAction.CREATE_RECOVERY_LINK.value}:
            base += 0.14
        elif action == RecoveryAction.WAIT_FOR_RETRY.value:
            base -= 0.22
    elif reason == FailureReason.MANDATE_CANCELLED.value:
        if action in {RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE.value, RecoveryAction.CREATE_RECOVERY_LINK.value}:
            base += 0.24
        elif action == RecoveryAction.WAIT_FOR_RETRY.value:
            base -= 0.32
    elif reason == FailureReason.UNKNOWN.value:
        base += 0.10 if action == RecoveryAction.ESCALATE_HUMAN.value else -0.18

    if status == "halted":
        if action == RecoveryAction.CREATE_RECOVERY_LINK.value:
            base += 0.18
        if action == RecoveryAction.WAIT_FOR_RETRY.value:
            base -= 0.24
    elif status == "pending" and action == RecoveryAction.WAIT_FOR_RETRY.value:
        base += 0.10

    base += min(case["prior_successes"], 12) * 0.012
    base -= case["contacts_7d"] * 0.075
    base -= max(case["retry_count"] - 1, 0) * 0.035
    base -= max(case["previous_interventions"] - 1, 0) * 0.025
    return max(0.01, min(0.96, base))


def outcome_for(case: dict, action: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{case['case_id']}:{action}".encode()).digest()
    draw = int.from_bytes(digest[:8], "big") / (2**64 - 1)
    return int(draw < ground_truth_probability(case, action))


def generate_case(rng: Random, index: int, prefix: str = "synthetic") -> dict:
    status = "halted" if rng.random() < 0.42 else "pending"
    reason = rng.choices(
        FAILURE_REASONS,
        weights=[28, 17, 18, 14, 13, 10],
        k=1,
    )[0]
    return {
        "case_id": f"{prefix}_{index:04d}",
        "status": status,
        "failure_reason": reason,
        "amount_rupees": float(rng.choice([199, 299, 499, 799, 999, 1499, 2499, 4999])),
        "days_overdue": rng.randint(0, 16),
        "retry_count": rng.randint(1, 5),
        "prior_successes": rng.randint(0, 18),
        "previous_interventions": rng.randint(0, 4),
        "contacts_7d": rng.randint(0, 4),
    }


def generate_training_records(count: int = 2_000, seed: int = 42) -> list[dict]:
    rng = Random(seed)
    rows: list[dict] = []
    for index in range(count):
        case = generate_case(rng, index, "train")
        action = rng.choice(ACTIONS)
        probability = ground_truth_probability(case, action)
        row = SyntheticRecord(
            **case,
            action=action,
            recovered=int(rng.random() < probability),
        )
        rows.append(asdict(row))
    return rows


def generate_evaluation_cases(count: int, seed: int) -> list[dict]:
    rng = Random(seed)
    return [generate_case(rng, index, f"eval_{seed}") for index in range(count)]


ACTION_COST_RUPEES = {
    RecoveryAction.WAIT_FOR_RETRY.value: 0.0,
    RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE.value: 6.0,
    RecoveryAction.CREATE_RECOVERY_LINK.value: 3.0,
    RecoveryAction.ESCALATE_HUMAN.value: 75.0,
    RecoveryAction.STOP_CONTACT.value: 0.0,
}


def expected_value(case: dict, action: str, probability: float) -> float:
    contact_penalty = case["contacts_7d"] * 5 if action in {
        RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE.value,
        RecoveryAction.CREATE_RECOVERY_LINK.value,
    } else 0
    return probability * case["amount_rupees"] - ACTION_COST_RUPEES[action] - contact_penalty


def model_features(case: dict, action: str) -> dict:
    return {
        "status": case["status"],
        "failure_reason": case["failure_reason"],
        "status_action": f"{case['status']}::{action}",
        "reason_action": f"{case['failure_reason']}::{action}",
        "amount_log": math.log1p(case["amount_rupees"]),
        "days_overdue": case["days_overdue"],
        "retry_count": case["retry_count"],
        "prior_successes": case["prior_successes"],
        "previous_interventions": case["previous_interventions"],
        "contacts_7d": case["contacts_7d"],
        "action": action,
    }
