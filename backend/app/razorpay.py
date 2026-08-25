from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .config import Settings


@dataclass(slots=True)
class PaymentLinkResult:
    id: str
    url: str
    adapter: str


class RazorpayGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_recovery_link(self, case: dict) -> PaymentLinkResult:
        if case["status"] != "halted":
            raise ValueError("Recovery links may only be created for halted subscriptions")
        if case.get("active_recovery_link_id"):
            raise ValueError("An active recovery link already exists")

        reference = f"pm-{case['id'][-20:]}"
        if not self.settings.razorpay_enabled:
            if not self.settings.demo_mode:
                raise RuntimeError("Razorpay test credentials are not configured")
            return PaymentLinkResult(
                id=f"plink_demo_{case['id'][-12:]}",
                url=f"https://example.invalid/pay/{reference}",
                adapter="demo",
            )

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
        auth = (self.settings.razorpay_key_id, self.settings.razorpay_key_secret)
        existing_response = httpx.get(
            "https://api.razorpay.com/v1/payment_links",
            auth=auth,
            params={"reference_id": reference},
            timeout=12,
        )
        existing_response.raise_for_status()
        existing_links = existing_response.json().get("payment_links", [])
        if existing_links:
            exact = [
                link for link in existing_links
                if link.get("reference_id") == reference
                and link.get("amount") == case["amount_paise"]
                and link.get("currency") == "INR"
                and link.get("status") in {"created", "issued", "partially_paid"}
                and isinstance(link.get("notes"), dict)
                and link["notes"].get("paymender_case_id") == case["id"]
                and link["notes"].get("subscription_id") == case["subscription_id"]
                and isinstance(link.get("id"), str)
                and isinstance(link.get("short_url"), str)
            ]
            if len(exact) != 1 or len(existing_links) != 1:
                raise RuntimeError("A conflicting Razorpay Payment Link already uses this recovery reference")
            return PaymentLinkResult(id=exact[0]["id"], url=exact[0]["short_url"], adapter="razorpay-test")

        response = httpx.post(
            "https://api.razorpay.com/v1/payment_links",
            auth=auth,
            json=payload,
            timeout=12,
        )
        response.raise_for_status()
        body = response.json()
        return PaymentLinkResult(id=body["id"], url=body["short_url"], adapter="razorpay-test")
