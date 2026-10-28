"""Confidence-based routing: automate the tickets the model is sure about, escalate the rest."""

from __future__ import annotations

import numpy as np


def routing_curve(y_true, y_pred, confidence, thresholds=None):
    """For each threshold: share of tickets automated and accuracy on that automated share."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    confidence = np.asarray(confidence, dtype=float)
    if thresholds is None:
        thresholds = np.linspace(0.2, 0.99, 80)
    coverage, accuracy = [], []
    for threshold in thresholds:
        automated = confidence >= threshold
        coverage.append(float(automated.mean()))
        accuracy.append(float((y_true[automated] == y_pred[automated]).mean()) if automated.any() else float("nan"))
    return np.asarray(thresholds), np.asarray(coverage), np.asarray(accuracy)


def choose_threshold(y_true, y_pred, confidence, target_accuracy: float = 0.95, min_coverage: float = 0.0) -> float:
    """Smallest confidence threshold whose automated tickets meet ``target_accuracy``.

    Choose it on out-of-fold predictions from the *training* data, never on the test set.
    Falls back to the strictest threshold tried if the target is unreachable.
    """
    thresholds, coverage, accuracy = routing_curve(y_true, y_pred, confidence)
    for threshold, cov, acc in zip(thresholds, coverage, accuracy):
        if cov >= min_coverage and not np.isnan(acc) and acc >= target_accuracy:
            return float(threshold)
    return float(thresholds[-1])


def apply_threshold(y_true, y_pred, confidence, threshold: float) -> dict[str, float]:
    """Outcome of routing at a fixed threshold."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    automated = np.asarray(confidence, dtype=float) >= threshold
    return {
        "threshold": float(threshold),
        "coverage": float(automated.mean()),
        "automated_accuracy": float((y_true[automated] == y_pred[automated]).mean()) if automated.any() else float("nan"),
        "escalated": int((~automated).sum()),
        "overall_accuracy_all_automated": float((y_true == y_pred).mean()),
    }
