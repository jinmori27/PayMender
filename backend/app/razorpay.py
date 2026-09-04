from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

from .config import Settings


@dataclass(slots=True)
class PaymentLinkResult:
    id: str
    url: str
    adapter: str


@dataclass(frozen=True, slots=True)
class ProviderSubscriptionContext:
    subscription_id: str
    invoice_id: str
    order_id: str | None
    amount_paise: int
    currency: str
    failure_reason: str
    retry_count: int
    prior_successes: int


MAX_PROVIDER_ITEMS = 100
MAX_AMOUNT_PAISE = 1_000_000_000


def _canonical_failure_reason(value: object) -> str:
    reason = str(value or "unknown").lower()
    mapping = {
        "insufficient": "insufficient_funds",
        "expired": "expired_card",
        "downtime": "issuer_downtime",
        "issuer_down": "issuer_downtime",
        "blocked": "bank_blocked",
        "mandate": "mandate_cancelled",
    }
    canonical = next((mapped for token, mapped in mapping.items() if token in reason), "unknown")
    return canonical


def _bounded_items(body: object, resource: str) -> list[dict]:
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise RuntimeError(f"Razorpay returned an invalid {resource} collection")
    items = body["items"]
    if len(items) > MAX_PROVIDER_ITEMS or any(not isinstance(item, dict) for item in items):
        raise RuntimeError(f"Razorpay returned an invalid {resource} collection")
    return items


class RazorpayGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def _auth(self) -> tuple[str, str]:
        if not self.settings.external_razorpay_enabled:
            raise RuntimeError("Razorpay test credentials are not configured")
        return self.settings.razorpay_key_id, self.settings.razorpay_key_secret

    def _validated_payment_link(self, body: object, case: dict, reference: str) -> PaymentLinkResult:
        if not isinstance(body, dict):
            raise RuntimeError("Razorpay Payment Link response is invalid")
        link_id = body.get("id")
        raw_url = body.get("short_url")
        notes = body.get("notes")
        matches = (
            isinstance(link_id, str)
            and link_id.startswith("plink_")
            and len(link_id) <= 120
            and body.get("reference_id") == reference
            and body.get("amount") == case["amount_paise"]
            and body.get("currency") == "INR"
            and body.get("status") == "created"
            and isinstance(notes, dict)
            and notes.get("paymender_case_id") == case["id"]
            and notes.get("subscription_id") == case["subscription_id"]
            and notes.get("mode") == "test-only"
        )
        if not matches:
            raise RuntimeError("Razorpay Payment Link response does not match the approved action")
        if not isinstance(raw_url, str):
            raise RuntimeError("Razorpay Payment Link URL is invalid")
        try:
            parsed = urlsplit(raw_url)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError as exc:
            raise RuntimeError("Razorpay Payment Link URL is invalid") from exc
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or host not in self.settings.payment_link_hosts
            or not parsed.path
        ):
            raise RuntimeError("Razorpay Payment Link URL is invalid")
        return PaymentLinkResult(id=link_id, url=raw_url, adapter="razorpay-test")

    def fetch_subscription_context(
        self,
        subscription_id: str,
        *,
        retry_count: int = 0,
        prior_successes: int = 0,
    ) -> ProviderSubscriptionContext:
        if not subscription_id.startswith("sub_") or len(subscription_id) > 80:
            raise ValueError("Razorpay subscription id is invalid")

        invoices_response = httpx.get(
            "https://api.razorpay.com/v1/invoices",
            auth=self._auth,
            params={"subscription_id": subscription_id},
            timeout=12,
        )
        invoices_response.raise_for_status()
        invoices = _bounded_items(invoices_response.json(), "invoice")
        actionable: list[dict] = []
        for invoice in invoices:
            if invoice.get("status") not in {"issued", "partially_paid"}:
                continue
            if invoice.get("subscription_id") != subscription_id:
                raise RuntimeError("Razorpay invoice subscription does not match the webhook")
            actionable.append(invoice)
        if not actionable:
            raise RuntimeError("No actionable Razorpay invoice exists for this subscription")

        invoice = max(actionable, key=lambda item: int(item.get("created_at") or 0))
        invoice_id = invoice.get("id")
        if not isinstance(invoice_id, str) or not invoice_id.startswith("inv_") or len(invoice_id) > 80:
            raise RuntimeError("Razorpay returned an invalid invoice id")
        if invoice.get("currency") != "INR":
            raise RuntimeError("Razorpay recovery invoices must use INR")

        raw_due = invoice.get("amount_due")
        if raw_due is None:
            gross = invoice.get("gross_amount", invoice.get("amount"))
            paid = invoice.get("amount_paid", 0)
            try:
                raw_due = int(gross) - int(paid)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Razorpay invoice amount is invalid") from exc
        try:
            amount_paise = int(raw_due)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Razorpay invoice amount is invalid") from exc
        if amount_paise <= 0 or amount_paise > MAX_AMOUNT_PAISE:
            raise RuntimeError("Razorpay invoice amount is outside the permitted range")

        order_id_value = invoice.get("order_id")
        order_id = order_id_value if isinstance(order_id_value, str) and order_id_value.startswith("order_") else None
        failure_reason = "unknown"
        if order_id:
            payments_response = httpx.get(
                f"https://api.razorpay.com/v1/orders/{order_id}/payments",
                auth=self._auth,
                timeout=12,
            )
            payments_response.raise_for_status()
            payments = _bounded_items(payments_response.json(), "payment")
            failed: list[dict] = []
            for payment in payments:
                payment_order = payment.get("order_id")
                if payment_order is not None and payment_order != order_id:
                    raise RuntimeError("Razorpay payment order does not match the invoice")
                if payment.get("status") == "failed":
                    failed.append(payment)
            if failed:
                latest = max(failed, key=lambda item: int(item.get("created_at") or 0))
                failure_reason = _canonical_failure_reason(
                    latest.get("error_reason") or latest.get("error_description")
                )

        return ProviderSubscriptionContext(
            subscription_id=subscription_id,
            invoice_id=invoice_id,
            order_id=order_id,
            amount_paise=amount_paise,
            currency="INR",
            failure_reason=failure_reason,
            retry_count=max(int(retry_count), 0),
            prior_successes=max(int(prior_successes), 0),
        )

    def create_recovery_link(self, case: dict) -> PaymentLinkResult:
        if case["status"] != "halted":
            raise ValueError("Recovery links may only be created for halted subscriptions")
        if case.get("active_recovery_link_id"):
            raise ValueError("An active recovery link already exists")

        reference = f"pm-{case['id'][-20:]}"
        if self.settings.demo_mode:
            return PaymentLinkResult(
                id=f"plink_demo_{case['id'][-12:]}",
                url=f"https://example.invalid/pay/{reference}",
                adapter="demo",
            )
        if not self.settings.razorpay_enabled:
            raise RuntimeError("Razorpay test credentials are not configured")

        payload = {
            "amount": case["amount_paise"],
            "currency": "INR",
            "accept_partial": False,
            "reference_id": reference,
            "description": f"Missed subscription payment for {case['subscription_id']}",
            "expire_by": int((datetime.now(timezone.utc) + timedelta(hours=48)).timestamp()),
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {
                "paymender_case_id": case["id"],
                "subscription_id": case["subscription_id"],
                "mode": "test-only",
            },
        }
        auth = self._auth
        existing_response = httpx.get(
            "https://api.razorpay.com/v1/payment_links",
            auth=auth,
            params={"reference_id": reference},
            timeout=12,
        )
        existing_response.raise_for_status()
        existing_body = existing_response.json()
        if not isinstance(existing_body, dict) or not isinstance(existing_body.get("payment_links"), list):
            raise RuntimeError("Razorpay returned an invalid Payment Link collection")
        existing_links = existing_body["payment_links"]
        if existing_links:
            if len(existing_links) != 1:
                raise RuntimeError("A conflicting Razorpay Payment Link already uses this recovery reference")
            try:
                return self._validated_payment_link(existing_links[0], case, reference)
            except RuntimeError as exc:
                raise RuntimeError(
                    "A conflicting Razorpay Payment Link already uses this recovery reference"
                ) from exc

        response = httpx.post(
            "https://api.razorpay.com/v1/payment_links",
            auth=auth,
            json=payload,
            timeout=12,
        )
        response.raise_for_status()
        body = response.json()
        return self._validated_payment_link(body, case, reference)
