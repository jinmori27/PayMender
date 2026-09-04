from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env.local", ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_display_name: str = "PayMender"
    app_env: str = "development"
    demo_mode: bool = True
    database_url: str = f"sqlite:///{(ROOT_DIR / 'paymender.sqlite3').as_posix()}"
    operator_api_token: str = ""
    max_webhook_body_bytes: int = Field(default=262_144, ge=1_024, le=1_048_576)
    webhook_rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)
    operator_session_rate_limit_per_15_minutes: int = Field(default=10, ge=1, le=1_000)
    evaluation_rate_limit_per_minute: int = Field(default=2, ge=1, le=100)
    rate_limit_max_keys: int = Field(default=10_000, ge=100, le=100_000)

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_seconds: int = Field(default=15, ge=1, le=60)
    gemini_max_output_tokens: int = Field(default=512, ge=64, le=2_048)

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_mode: str = "test"
    razorpay_payment_link_hosts: str = "rzp.io"
    max_real_payment_links: int = Field(default=5, ge=0, le=5)

    contact_cap_7d: int = 3
    min_recovery_amount_paise: int = 10_000
    worker_poll_seconds: float = 0.5
    job_lease_seconds: int = 60

    @model_validator(mode="after")
    def reject_live_mode(self) -> "Settings":
        if self.razorpay_mode.lower() != "test":
            raise ValueError("PayMender only permits RAZORPAY_MODE=test")
        if self.razorpay_key_id and not self.razorpay_key_id.startswith("rzp_test_"):
            raise ValueError("Only Razorpay test-mode key IDs are accepted")
        if self.operator_api_token and len(self.operator_api_token.strip()) < 24:
            raise ValueError("OPERATOR_API_TOKEN must contain at least 24 characters")
        return self

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def external_razorpay_enabled(self) -> bool:
        return not self.demo_mode and self.razorpay_enabled

    @property
    def payment_link_hosts(self) -> frozenset[str]:
        return frozenset(
            host.strip().lower().rstrip(".")
            for host in self.razorpay_payment_link_hosts.split(",")
            if host.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
