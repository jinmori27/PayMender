from __future__ import annotations

from app.config import get_settings
import pytest

from app.razorpay import RazorpayGateway


class StubResponse:
    def __init__(self, body: dict):
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


def live_settings():
    return get_settings().model_copy(update={
        "demo_mode": False,
        "razorpay_key_id": "rzp_test_example",
        "razorpay_key_secret": "secret",
    })


def recovery_case() -> dict:
    return {
        "id": "case_reconcile_1234567890",
        "subscription_id": "sub_reconcile",
        "status": "halted",
        "amount_paise": 99_900,
        "active_recovery_link_id": None,
    }


def test_demo_mode_never_calls_razorpay_even_when_credentials_exist(monkeypatch):
    settings = live_settings().model_copy(update={"demo_mode": True})
    monkeypatch.setattr(
        "app.razorpay.httpx.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network call in demo mode")),
    )
    monkeypatch.setattr(
        "app.razorpay.httpx.post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network call in demo mode")),
    )

    result = RazorpayGateway(settings).create_recovery_link(recovery_case())

    assert result.adapter == "demo"
    assert result.id.startswith("plink_demo_")


def test_existing_exact_payment_link_is_reused_without_post(monkeypatch):
    case = recovery_case()
    reference = f"pm-{case['id'][-20:]}"
    calls: list[str] = []

    def fake_get(*_args, **_kwargs):
        calls.append("get")
        return StubResponse({"payment_links": [{
            "id": "plink_existing",
            "short_url": "https://rzp.io/existing",
            "status": "created",
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
        "status": "created",
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


@pytest.mark.parametrize("url", [
    "http://rzp.io/insecure",
    "https://user:password@rzp.io/credentials",
    "https://untrusted.example/phish",
    "https://rzp.io:invalid/path",
])
def test_created_payment_link_rejects_untrusted_urls(monkeypatch, url):
    case = recovery_case()
    reference = f"pm-{case['id'][-20:]}"
    monkeypatch.setattr(
        "app.razorpay.httpx.get",
        lambda *_args, **_kwargs: StubResponse({"payment_links": []}),
    )
    monkeypatch.setattr(
        "app.razorpay.httpx.post",
        lambda *_args, **_kwargs: StubResponse({
            "id": "plink_created",
            "short_url": url,
            "status": "created",
            "amount": case["amount_paise"],
            "amount_paid": 0,
            "currency": "INR",
            "reference_id": reference,
            "notes": {
                "paymender_case_id": case["id"],
                "subscription_id": case["subscription_id"],
                "mode": "test-only",
            },
        }),
    )

    with pytest.raises(RuntimeError, match="URL"):
        RazorpayGateway(live_settings()).create_recovery_link(case)


def test_created_payment_link_rejects_mismatched_provider_fields(monkeypatch):
    case = recovery_case()
    reference = f"pm-{case['id'][-20:]}"
    monkeypatch.setattr(
        "app.razorpay.httpx.get",
        lambda *_args, **_kwargs: StubResponse({"payment_links": []}),
    )
    monkeypatch.setattr(
        "app.razorpay.httpx.post",
        lambda *_args, **_kwargs: StubResponse({
            "id": "plink_created",
            "short_url": "https://rzp.io/created",
            "status": "created",
            "amount": case["amount_paise"] + 1,
            "amount_paid": 0,
            "currency": "INR",
            "reference_id": reference,
            "notes": {
                "paymender_case_id": case["id"],
                "subscription_id": case["subscription_id"],
                "mode": "test-only",
            },
        }),
    )

    with pytest.raises(RuntimeError, match="does not match"):
        RazorpayGateway(live_settings()).create_recovery_link(case)


def test_created_payment_link_rejects_undocumented_status(monkeypatch):
    case = recovery_case()
    reference = f"pm-{case['id'][-20:]}"
    monkeypatch.setattr(
        "app.razorpay.httpx.get",
        lambda *_args, **_kwargs: StubResponse({"payment_links": []}),
    )
    monkeypatch.setattr(
        "app.razorpay.httpx.post",
        lambda *_args, **_kwargs: StubResponse({
            "id": "plink_created",
            "short_url": "https://rzp.io/created",
            "status": "issued",
            "amount": case["amount_paise"],
            "currency": "INR",
            "reference_id": reference,
            "notes": {
                "paymender_case_id": case["id"],
                "subscription_id": case["subscription_id"],
                "mode": "test-only",
            },
        }),
    )

    with pytest.raises(RuntimeError, match="does not match"):
        RazorpayGateway(live_settings()).create_recovery_link(case)


def test_subscription_context_uses_latest_actionable_invoice_and_failed_payment(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_get(url, *_args, **kwargs):
        calls.append((url, str(kwargs.get("params", ""))))
        if url.endswith("/v1/invoices"):
            return StubResponse({
                "entity": "collection",
                "count": 3,
                "items": [
                    {
                        "id": "inv_paid",
                        "subscription_id": "sub_provider_123456",
                        "status": "paid",
                        "currency": "INR",
                        "amount": 99_900,
                        "amount_due": 0,
                        "created_at": 100,
                    },
                    {
                        "id": "inv_old",
                        "subscription_id": "sub_provider_123456",
                        "status": "issued",
                        "currency": "INR",
                        "amount": 49_900,
                        "amount_due": 49_900,
                        "order_id": "order_old",
                        "created_at": 200,
                    },
                    {
                        "id": "inv_latest",
                        "subscription_id": "sub_provider_123456",
                        "status": "issued",
                        "currency": "INR",
                        "amount": 149_900,
                        "amount_due": 149_900,
                        "order_id": "order_latest",
                        "created_at": 300,
                        "customer_details": {"email": "discard@example.test", "contact": "+919999999999"},
                    },
                ],
            })
        if url.endswith("/v1/orders/order_latest/payments"):
            return StubResponse({
                "entity": "collection",
                "count": 2,
                "items": [
                    {"id": "pay_old", "status": "failed", "created_at": 310, "error_reason": "issuer_down"},
                    {
                        "id": "pay_latest",
                        "status": "failed",
                        "created_at": 320,
                        "error_reason": "card_expired",
                        "email": "discard-payment@example.test",
                        "contact": "+918888888888",
                    },
                ],
            })
        raise AssertionError(f"Unexpected Razorpay URL: {url}")

    monkeypatch.setattr("app.razorpay.httpx.get", fake_get)

    context = RazorpayGateway(live_settings()).fetch_subscription_context(
        "sub_provider_123456",
        retry_count=4,
        prior_successes=7,
    )

    assert context.subscription_id == "sub_provider_123456"
    assert context.invoice_id == "inv_latest"
    assert context.order_id == "order_latest"
    assert context.amount_paise == 149_900
    assert context.currency == "INR"
    assert context.failure_reason == "expired_card"
    assert context.retry_count == 4
    assert context.prior_successes == 7
    assert "discard" not in repr(context)
    assert len(calls) == 2


def test_subscription_context_rejects_provider_subscription_mismatch(monkeypatch):
    monkeypatch.setattr(
        "app.razorpay.httpx.get",
        lambda *_args, **_kwargs: StubResponse({
            "entity": "collection",
            "count": 1,
            "items": [{
                "id": "inv_wrong",
                "subscription_id": "sub_someone_else",
                "status": "issued",
                "currency": "INR",
                "amount_due": 99_900,
                "created_at": 1,
            }],
        }),
    )

    with pytest.raises(RuntimeError, match="subscription"):
        RazorpayGateway(live_settings()).fetch_subscription_context("sub_expected_123456")


def test_subscription_context_rejects_non_inr_invoice(monkeypatch):
    monkeypatch.setattr(
        "app.razorpay.httpx.get",
        lambda *_args, **_kwargs: StubResponse({
            "entity": "collection",
            "count": 1,
            "items": [{
                "id": "inv_usd",
                "subscription_id": "sub_expected_123456",
                "status": "issued",
                "currency": "USD",
                "amount_due": 99_900,
                "created_at": 1,
            }],
        }),
    )

    with pytest.raises(RuntimeError, match="INR"):
        RazorpayGateway(live_settings()).fetch_subscription_context("sub_expected_123456")
