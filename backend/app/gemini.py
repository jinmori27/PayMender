from __future__ import annotations

import json

from .config import Settings
from .schemas import ActionScore, FailureReason, GeminiDecision, RecoveryAction


GEMINI_CASE_FIELDS = (
    "status",
    "failure_reason",
    "amount_rupees",
    "days_overdue",
    "retry_count",
    "prior_successes",
    "previous_interventions",
    "contacts_7d",
    "next_retry_at",
)


def gemini_case_payload(case: dict) -> dict:
    return {field: case.get(field) for field in GEMINI_CASE_FIELDS}


def fallback_decision(case: dict, scores: list[ActionScore], reason: str = "offline") -> tuple[GeminiDecision, str]:
    top = scores[0]
    failure = FailureReason(case.get("failure_reason", "unknown"))
    explanation = (
        f"The subscription is {case['status']} after {case['retry_count']} attempt(s). "
        f"{top.action.value.replace('_', ' ').title()} has the highest estimated net recovery value, "
        "subject to deterministic safety checks."
    )
    english = (
        "Your subscription payment needs attention. No action has been taken yet. "
        "Please review the secure payment option when it is approved."
    )
    hinglish = (
        "Aapke subscription payment ko attention chahiye. Abhi koi action nahi liya gaya hai. "
        "Approval ke baad secure payment option review karein."
    )
    decision = GeminiDecision(
        diagnosis=failure,
        recommended_action=top.action,
        confidence=round(max(0.51, top.recovery_probability), 3),
        explanation=explanation,
        evidence=[
            f"subscription_status={case['status']}",
            f"failure_reason={case['failure_reason']}",
            f"retry_count={case['retry_count']}",
        ],
        message_english=english,
        message_hinglish=hinglish,
    )
    return decision, f"deterministic-fallback:{reason}"


class GeminiAdvisor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def propose(self, case: dict, scores: list[ActionScore]) -> tuple[GeminiDecision, str]:
        if not self.settings.gemini_enabled:
            return fallback_decision(case, scores, "no-key")

        prompt = {
            "role": "You are a cautious subscription revenue-recovery analyst with no execution authority.",
            "rules": [
                "Choose only one allowed RecoveryAction enum value.",
                "Use only the supplied evidence; do not invent customer facts.",
                "Do not promise a discount, successful payment, or automatic action.",
                "Messages must be calm, non-coercive, and clearly say no action has occurred yet.",
            ],
            "case": gemini_case_payload(case),
            "model_scores": [score.model_dump() for score in scores],
        }
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=self.settings.gemini_timeout_seconds * 1_000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            for model_name in (self.settings.gemini_model, self.settings.gemini_fallback_model):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=json.dumps(prompt),
                        config=types.GenerateContentConfig(
                            max_output_tokens=self.settings.gemini_max_output_tokens,
                            response_mime_type="application/json",
                            response_schema=GeminiDecision,
                        ),
                    )
                    return GeminiDecision.model_validate_json(response.text), f"gemini:{model_name}"
                except Exception:
                    if model_name == self.settings.gemini_fallback_model:
                        raise
        except Exception as exc:
            safe_reason = type(exc).__name__
            return fallback_decision(case, scores, safe_reason)

        return fallback_decision(case, scores, "unreachable")
