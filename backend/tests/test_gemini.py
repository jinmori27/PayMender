from __future__ import annotations

from google import genai

from app.config import Settings
from app.gemini import GeminiAdvisor, gemini_case_payload
from app.ml import recovery_model


CASE = {
    "id": "case_gemini_test",
    "subscription_id": "sub_gemini_test",
    "customer_name": "Synthetic Customer",
    "status": "halted",
    "failure_reason": "expired_card",
    "amount_paise": 149_900,
    "amount_rupees": 1_499,
    "days_overdue": 6,
    "retry_count": 4,
    "prior_successes": 12,
    "previous_interventions": 0,
    "contacts_7d": 1,
    "next_retry_at": None,
    "recovered_amount_paise": 0,
    "active_recovery_link_id": None,
    "active_recovery_link_url": None,
}


class FakeClient:
    def __init__(self, *_args, **_kwargs):
        self.models = self

    def generate_content(self, **_kwargs):
        raise TimeoutError("simulated provider timeout")


class MalformedClient(FakeClient):
    def generate_content(self, **_kwargs):
        return type("Response", (), {"text": "{}"})()


def configured_settings() -> Settings:
    return Settings(gemini_api_key="test-key", database_url="sqlite://")


def test_gemini_timeout_falls_back_without_changing_action_scores(monkeypatch):
    scores = recovery_model.score_actions(CASE)
    monkeypatch.setattr(genai, "Client", FakeClient)

    decision, provider = GeminiAdvisor(configured_settings()).propose(CASE, scores)

    assert decision.recommended_action == scores[0].action
    assert provider == "deterministic-fallback:TimeoutError"


def test_gemini_malformed_output_falls_back_to_valid_schema(monkeypatch):
    scores = recovery_model.score_actions(CASE)
    monkeypatch.setattr(genai, "Client", MalformedClient)

    decision, provider = GeminiAdvisor(configured_settings()).propose(CASE, scores)

    assert decision.evidence
    assert decision.message_english
    assert provider == "deterministic-fallback:ValidationError"


def test_gemini_receives_only_allowlisted_non_identifying_case_fields():
    safe_case = gemini_case_payload({
        **CASE,
        "customer_name": "Do Not Send",
        "active_recovery_link_url": "https://secret-link.example.test",
        "unexpected_private_field": "private",
    })

    assert safe_case["status"] == "halted"
    assert "customer_name" not in safe_case
    assert "active_recovery_link_url" not in safe_case
    assert "unexpected_private_field" not in safe_case
