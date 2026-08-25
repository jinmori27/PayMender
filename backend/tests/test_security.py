from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


OPERATOR_HEADERS = {"X-Operator-Token": "test_operator_token_32_bytes_long"}


def test_operator_endpoints_require_a_valid_token():
    client = TestClient(app)

    assert client.get("/api/cases").status_code == 401
    assert client.post("/api/demo/reset").status_code == 401
    assert client.get("/api/cases", headers={"X-Operator-Token": "wrong"}).status_code == 401
    assert client.get("/api/cases", headers=OPERATOR_HEADERS).status_code == 200


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
