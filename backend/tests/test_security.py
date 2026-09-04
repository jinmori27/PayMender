from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, rate_limiter, settings


OPERATOR_HEADERS = {"X-Operator-Token": "test_operator_token_32_bytes_long"}


def test_operator_endpoints_require_a_valid_token():
    client = TestClient(app)

    assert client.get("/api/cases").status_code == 401
    assert client.post("/api/demo/reset").status_code == 401
    assert client.get("/api/cases", headers={"X-Operator-Token": "wrong"}).status_code == 401
    assert client.get("/api/cases", headers=OPERATOR_HEADERS).status_code == 200


def test_operator_session_is_rate_limited_with_retry_after(monkeypatch):
    rate_limiter.clear()
    monkeypatch.setattr(settings, "operator_session_rate_limit_per_15_minutes", 2)
    client = TestClient(app)

    assert client.get("/api/operator/session", headers={"X-Operator-Token": "wrong"}).status_code == 401
    assert client.get("/api/operator/session", headers={"X-Operator-Token": "wrong"}).status_code == 401
    limited = client.get("/api/operator/session", headers={"X-Operator-Token": "wrong"})

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    rate_limiter.clear()


def test_operator_session_validates_token_without_returning_secrets():
    client = TestClient(app)

    response = client.get("/api/operator/session", headers=OPERATOR_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_spa_fallback_cannot_escape_static_directory():
    client = TestClient(app)

    response = client.get("/%2e%2e/%2e%2e/.env.local")

    assert response.status_code == 404


def test_security_headers_are_added_to_api_responses():
    response = TestClient(app).get("/api/health")

    assert response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_public_health_is_minimal_and_configuration_health_requires_operator():
    client = TestClient(app)

    public = client.get("/api/health")
    protected = client.get("/api/health/details")
    authorized = client.get("/api/health/details", headers=OPERATOR_HEADERS)

    assert public.json() == {"status": "ok", "display_name": "PayMender"}
    assert protected.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["operator_auth"] == "configured"


def test_webhook_rate_limit_applies_before_signature_work(monkeypatch):
    rate_limiter.clear()
    monkeypatch.setattr(settings, "webhook_rate_limit_per_minute", 2)
    client = TestClient(app)
    headers = {
        "X-Razorpay-Event-Id": "evt_rate_limited",
        "X-Razorpay-Signature": "0" * 64,
    }

    assert client.post("/api/webhooks/razorpay", content=b"{}", headers=headers).status_code == 401
    assert client.post("/api/webhooks/razorpay", content=b"{}", headers=headers).status_code == 401
    limited = client.post("/api/webhooks/razorpay", content=b"{}", headers=headers)

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    rate_limiter.clear()


def test_evaluation_rate_limit_is_operator_protected(monkeypatch):
    rate_limiter.clear()
    monkeypatch.setattr(settings, "evaluation_rate_limit_per_minute", 1)
    client = TestClient(app)
    monkeypatch.setattr("app.main.save_evaluation", lambda _db, _settings: {
        "id": "eval_rate_limit",
        "label": "contained",
        "synthetic_disclaimer": "Synthetic test fixture",
        "train_records": 1,
        "batches": 1,
        "cases_per_batch": 1,
        "policies": [],
        "created_at": "2026-01-01T00:00:00Z",
    })

    assert client.post("/api/evaluations", headers=OPERATOR_HEADERS).status_code == 200
    limited = client.post("/api/evaluations", headers=OPERATOR_HEADERS)

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    rate_limiter.clear()


def test_webhook_rejects_body_larger_than_configured_limit():
    response = TestClient(app).post(
        "/api/webhooks/razorpay",
        content=b"x" * 300_000,
        headers={
            "Content-Length": "300000",
            "X-Razorpay-Event-Id": "evt_oversized",
            "X-Razorpay-Signature": "0" * 64,
        },
    )

    assert response.status_code == 413
