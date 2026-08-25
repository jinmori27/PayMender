from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev
from uuid import uuid4

from .config import Settings
from .ml import RecoveryModel
from .policy import decide_policy
from .schemas import EvaluationPolicyMetrics, EvaluationSummary, RecoveryAction
from .synthetic import (
    ACTION_COST_RUPEES,
    generate_evaluation_cases,
    outcome_for,
)


POLICIES = ["PayMender", "Always wait", "Always recovery link", "Fixed rules"]


def fixed_rules(case: dict) -> RecoveryAction:
    if case["contacts_7d"] >= 3:
        return RecoveryAction.STOP_CONTACT
    if case["failure_reason"] == "issuer_downtime" and case["status"] == "pending":
        return RecoveryAction.WAIT_FOR_RETRY
    if case["failure_reason"] in {"expired_card", "mandate_cancelled"}:
        return RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE
    if case["status"] == "halted":
        return RecoveryAction.CREATE_RECOVERY_LINK
    return RecoveryAction.ESCALATE_HUMAN


def _policy_action(name: str, case: dict, model: RecoveryModel, settings: Settings) -> tuple[RecoveryAction, int]:
    if name == "Always wait":
        proposed = RecoveryAction.WAIT_FOR_RETRY
    elif name == "Always recovery link":
        proposed = RecoveryAction.CREATE_RECOVERY_LINK
    elif name == "Fixed rules":
        proposed = fixed_rules(case)
    else:
        proposed = model.score_actions(case)[0].action

    policy_case = {
        **case,
        "amount_paise": int(case["amount_rupees"] * 100),
        "recovered_amount_paise": 0,
        "active_recovery_link_id": None,
        "next_retry_at": None,
    }
    decision = decide_policy(policy_case, proposed, 0.75, settings)
    return decision.action, int(decision.overridden)


def run_evaluation(model: RecoveryModel, settings: Settings) -> EvaluationSummary:
    batch_results: dict[str, list[dict[str, float]]] = defaultdict(list)
    for batch_index, seed in enumerate(range(1_000, 1_010)):
        cases = generate_evaluation_cases(200, seed)
        for policy_name in POLICIES:
            gross = 0.0
            net = 0.0
            recovered_count = 0
            contacts = 0
            escalations = 0
            stopped = 0
            blocked = 0
            for case in cases:
                action, override = _policy_action(policy_name, case, model, settings)
                blocked += override
                action_value = action.value
                recovered = outcome_for(case, action_value, seed + batch_index)
                amount = case["amount_rupees"] if recovered else 0.0
                cost = ACTION_COST_RUPEES[action_value]
                gross += amount
                net += amount - cost
                recovered_count += recovered
                contacts += int(action in {
                    RecoveryAction.REQUEST_PAYMENT_METHOD_UPDATE,
                    RecoveryAction.CREATE_RECOVERY_LINK,
                })
                escalations += int(action == RecoveryAction.ESCALATE_HUMAN)
                stopped += int(action == RecoveryAction.STOP_CONTACT)
            batch_results[policy_name].append({
                "gross": gross,
                "net": net,
                "rate": recovered_count / len(cases),
                "contacts_per_recovery": contacts / max(recovered_count, 1),
                "escalation_rate": escalations / len(cases),
                "stopped": float(stopped),
                "blocked": float(blocked),
            })

    policies: list[EvaluationPolicyMetrics] = []
    for name in POLICIES:
        rows = batch_results[name]
        policies.append(EvaluationPolicyMetrics(
            policy=name,
            gross_recovered_mean=round(mean(row["gross"] for row in rows), 2),
            gross_recovered_std=round(pstdev(row["gross"] for row in rows), 2),
            net_recovered_mean=round(mean(row["net"] for row in rows), 2),
            net_recovered_std=round(pstdev(row["net"] for row in rows), 2),
            recovery_rate_mean=round(mean(row["rate"] for row in rows), 4),
            contacts_per_recovery_mean=round(mean(row["contacts_per_recovery"] for row in rows), 3),
            escalation_rate_mean=round(mean(row["escalation_rate"] for row in rows), 4),
            stopped_mean=round(mean(row["stopped"] for row in rows), 2),
            unsafe_blocked_mean=round(mean(row["blocked"] for row in rows), 2),
        ))

    return EvaluationSummary(
        id=f"eval_{uuid4().hex}",
        label="10 × 200 held-out synthetic subscription cases",
        synthetic_disclaimer="Synthetic counterfactual simulation; not a claim of real merchant uplift.",
        train_records=2_000,
        batches=10,
        cases_per_batch=200,
        policies=policies,
        created_at=datetime.now(timezone.utc),
    )
