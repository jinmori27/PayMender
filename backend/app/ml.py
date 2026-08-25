from __future__ import annotations

from pathlib import Path
from threading import Lock

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .schemas import ActionScore, RecoveryAction
from .synthetic import ACTIONS, expected_value, generate_training_records, model_features


ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "recovery_model.joblib"
CATEGORICAL = ["status", "failure_reason", "status_action", "reason_action", "action"]
NUMERICAL = [
    "amount_log",
    "days_overdue",
    "retry_count",
    "prior_successes",
    "previous_interventions",
    "contacts_7d",
]
FEATURES = CATEGORICAL + NUMERICAL


class RecoveryModel:
    def __init__(self) -> None:
        self.pipeline: Pipeline | None = None
        self._lock = Lock()

    def ensure_loaded(self) -> None:
        if self.pipeline is not None:
            return
        with self._lock:
            if self.pipeline is not None:
                return
            if ARTIFACT_PATH.exists():
                self.pipeline = joblib.load(ARTIFACT_PATH)
            else:
                self.pipeline = self.train(save=False)

    def train(self, save: bool = True) -> Pipeline:
        rows = generate_training_records()
        matrix = [[model_features(row, row["action"])[name] for name in FEATURES] for row in rows]
        labels = np.array([row["recovered"] for row in rows])
        preprocessor = ColumnTransformer([
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(range(len(CATEGORICAL)))),
            ("numeric", StandardScaler(), list(range(len(CATEGORICAL), len(FEATURES)))),
        ])
        pipeline = Pipeline([
            ("features", preprocessor),
            ("classifier", LogisticRegression(max_iter=600, random_state=42)),
        ])
        pipeline.fit(matrix, labels)
        self.pipeline = pipeline
        if save:
            ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(pipeline, ARTIFACT_PATH)
        return pipeline

    def score_actions(self, case: dict) -> list[ActionScore]:
        self.ensure_loaded()
        assert self.pipeline is not None
        matrix = [[model_features(case, action)[name] for name in FEATURES] for action in ACTIONS]
        probabilities = self.pipeline.predict_proba(matrix)[:, 1]
        scores = [
            ActionScore(
                action=RecoveryAction(action),
                recovery_probability=float(probability),
                expected_value_rupees=round(expected_value(case, action, float(probability)), 2),
            )
            for action, probability in zip(ACTIONS, probabilities, strict=True)
        ]
        return sorted(scores, key=lambda item: item.expected_value_rupees, reverse=True)


recovery_model = RecoveryModel()
