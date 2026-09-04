from __future__ import annotations

import inspect

from app.config import get_settings
from app.evaluation import run_evaluation
from app.ml import RecoveryModel


def test_recovery_model_never_deserializes_a_runtime_artifact():
    assert "joblib" not in inspect.getsource(RecoveryModel.ensure_loaded)


def test_evaluation_is_reproducible_and_honest():
    model = RecoveryModel()
    first = run_evaluation(model, get_settings())
    second = run_evaluation(model, get_settings())
    assert first.synthetic_disclaimer.startswith("Synthetic")
    assert first.train_records == 2_000
    assert first.batches == 10
    assert first.cases_per_batch == 200
    assert [item.model_dump() for item in first.policies] == [item.model_dump() for item in second.policies]
    assert {item.policy for item in first.policies} == {"PayMender", "Always wait", "Always recovery link", "Fixed rules"}
