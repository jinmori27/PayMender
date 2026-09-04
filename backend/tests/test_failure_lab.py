from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


OPERATOR_HEADERS = {"X-Operator-Token": "test_operator_token_32_bytes_long"}


@pytest.mark.parametrize(
    "scenario",
    ["duplicate", "gemini-quota", "razorpay-500", "worker-crash"],
)
def test_reliability_lab_executes_contained_scenarios_without_network(monkeypatch, scenario):
    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("Reliability Lab attempted an outbound network call")

    monkeypatch.setattr("app.razorpay.httpx.get", unexpected_network)
    monkeypatch.setattr("app.razorpay.httpx.post", unexpected_network)

    response = TestClient(app).post(
        f"/api/demo/failures/{scenario}",
        headers=OPERATOR_HEADERS,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["scenario"] == scenario
    assert result["status"] == "contained"
    assert result["evidence_ids"]
    assert result["assertions"]
    assert all(result["assertions"].values())
