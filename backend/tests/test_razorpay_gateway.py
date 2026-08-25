from __future__ import annotations

from app.config import get_settings
from app.razorpay import RazorpayGateway


class StubResponse:
    def __init__(self, body: dict):
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


def live_settings():
    return get_settings().model_copy(update={"razorpay_key_id": "rzp_test_example", "razorpay_key_secret": "secret"})


def recovery_case() -> dict:
    return {
        "id": "case_reconcile_1234567890",
        "subscription_id": "sub_reconcile",
        "status": "halted",
        "amount_paise": 99_900,
        "active_recovery_link_id": None,
    }


def test_existing_exact_payment_link_is_reused_without_post(monkeypatch):
    case = recovery_case()
    reference = f"pm-{case['id'][-20:]}"
    calls: list[str] = []

    def fake_get(*_args, **_kwargs):
        calls.append("get")
        return StubResponse({"payment_links": [{
            "id": "plink_existing",
            "short_url": "https://rzp.io/existing",
            "status": "issued",
            "amount": case["amount_paise"],
            "amount_paid": 0,
            "currency": "INR",
            "reference_id": reference,
            "notes": {"paymender_case_id": case["id"], "subscription_id": case["subscription_id"], "mode": "test-only"},
        }]})

    monkeypatch.setattr("app.razorpay.httpx.get", fake_get)
    monkeypatch.setattr("app.razorpay.httpx.post", lambda *_args, **_kwargs: calls.append("post"))

    result = RazorpayGateway(live_settings()).create_recovery_link(case)

    assert result.id == "plink_existing"
    assert calls == ["get"]


def test_conflicting_existing_reference_fails_closed(monkeypatch):
    case = recovery_case()
    reference = f"pm-{case['id'][-20:]}"
    monkeypatch.setattr("app.razorpay.httpx.get", lambda *_args, **_kwargs: StubResponse({"payment_links": [{
        "id": "plink_conflict",
        "short_url": "https://rzp.io/conflict",
        "status": "issued",
        "amount": 1,
        "currency": "INR",
        "reference_id": reference,
        "notes": {"paymender_case_id": "case_wrong"},
    }]}))

    try:
        RazorpayGateway(live_settings()).create_recovery_link(case)
    except RuntimeError as exc:
        assert "conflicting" in str(exc).lower()
    else:
        raise AssertionError("Conflicting Razorpay reference was reused")
