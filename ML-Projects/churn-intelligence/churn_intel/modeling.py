"""Model zoo, evaluation metrics and calibration helpers."""

from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import CATEGORICAL, NUMERIC


def make_preprocessor() -> ColumnTransformer:
    """Impute (with missing-value flags), scale numerics and one-hot categoricals."""
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    return ColumnTransformer([("num", numeric, NUMERIC), ("cat", categorical, CATEGORICAL)])


def model_zoo(seed: int = 7, quick: bool = False) -> dict[str, Pipeline]:
    """Three model families with deliberately different inductive biases."""
    trees = 80 if quick else 300
    return {
        "Logistic regression": Pipeline(
            [
                ("prep", make_preprocessor()),
                ("clf", LogisticRegression(max_iter=2000, C=0.5)),
            ]
        ),
        "Random forest": Pipeline(
            [
                ("prep", make_preprocessor()),
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=trees,
                        min_samples_leaf=20,
                        max_features="sqrt",
                        n_jobs=1,
                        random_state=seed,
                    ),
                ),
            ]
        ),
        "Gradient boosting": Pipeline(
            [
                ("prep", make_preprocessor()),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        learning_rate=0.06,
                        max_iter=120 if quick else 250,
                        max_leaf_nodes=15,
                        min_samples_leaf=40,
                        l2_regularization=1.0,
                        early_stopping=True,
                        validation_fraction=0.15,
                        random_state=seed,
                    ),
                ),
            ]
        ),
    }


def expected_calibration_error(y_true, y_prob, bins: int = 10) -> float:
    """Equal-frequency expected calibration error (lower is better)."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    edges = np.quantile(y_prob, np.linspace(0, 1, bins + 1))
    index = np.clip(np.searchsorted(edges, y_prob, side="right") - 1, 0, bins - 1)
    total = 0.0
    for b in range(bins):
        mask = index == b
        if mask.any():
            total += abs(y_true[mask].mean() - y_prob[mask].mean()) * mask.sum() / len(y_true)
    return float(total)


def evaluate_probabilities(y_true, y_prob) -> dict[str, float]:
    """Ranking quality (ROC/PR AUC) and probability quality (Brier, log loss, ECE)."""
    y_true = np.asarray(y_true)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1 - 1e-6)
    return {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob)),
        "ece": expected_calibration_error(y_true, y_prob),
    }
