"""Turn churn probabilities into a retention-campaign decision.

A model score is only useful once it drives an action. Here the action is
"send a retention offer", which costs money and only works some of the time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RetentionEconomics:
    """Assumptions behind the campaign (all editable, all stated in the report)."""

    contact_cost: float = 25.0  # cost of one offer, paid for every contacted customer
    save_rate: float = 0.35  # chance the offer keeps a customer who would have left
    customer_value: float = 480.0  # margin retained when a churner is saved

    def __post_init__(self) -> None:
        if self.contact_cost < 0 or self.customer_value <= 0:
            raise ValueError("contact_cost must be >= 0 and customer_value must be > 0")
        if not 0 < self.save_rate <= 1:
            raise ValueError("save_rate must be in (0, 1]")

    @property
    def breakeven_probability(self) -> float:
        """Contact a customer only if p * save_rate * value exceeds the offer cost."""
        return self.contact_cost / (self.save_rate * self.customer_value)


def campaign_profit(y_true, contacted, economics: RetentionEconomics) -> float:
    """Expected profit of contacting the customers flagged in ``contacted``."""
    y_true = np.asarray(y_true, dtype=float)
    contacted = np.asarray(contacted, dtype=bool)
    gain = y_true * economics.save_rate * economics.customer_value - economics.contact_cost
    return float(gain[contacted].sum())


def profit_curve(y_true, scores, economics: RetentionEconomics, thresholds=None):
    """Profit when contacting everyone whose score is at or above each threshold."""
    scores = np.asarray(scores, dtype=float)
    if thresholds is None:
        thresholds = np.linspace(0.0, 1.0, 201)
    thresholds = np.asarray(thresholds, dtype=float)
    profits = np.array([campaign_profit(y_true, scores >= t, economics) for t in thresholds])
    return thresholds, profits


def best_threshold(y_true, scores, economics: RetentionEconomics) -> tuple[float, float]:
    """Return ``(threshold, profit)`` maximising realised profit on the given data."""
    thresholds, profits = profit_curve(y_true, scores, economics)
    best = int(np.argmax(profits))
    return float(thresholds[best]), float(profits[best])


def lift_table(y_true, scores, bins: int = 10):
    """Decile table: churn rate, lift over the base rate and cumulative capture."""
    y_true = np.asarray(y_true, dtype=float)
    order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
    sorted_y = y_true[order]
    base_rate = y_true.mean()
    total_positive = y_true.sum()
    rows = []
    captured = 0.0
    for chunk in np.array_split(sorted_y, bins):
        captured += chunk.sum()
        rows.append(
            {
                "decile": len(rows) + 1,
                "customers": int(len(chunk)),
                "churn_rate": float(chunk.mean()),
                "lift": float(chunk.mean() / base_rate) if base_rate else 0.0,
                "cumulative_capture": float(captured / total_positive) if total_positive else 0.0,
            }
        )
    return rows
