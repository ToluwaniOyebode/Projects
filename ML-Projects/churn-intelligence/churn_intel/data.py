"""Synthetic subscription-business customer data.

The generator encodes a believable causal story (contracts, tenure, price,
service quality and payment friction drive churn) plus realistic mess: missing
values, an interaction effect and label noise. Real customer data is private, so
a transparent generator lets anyone reproduce the whole project from one seed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET = "churned"
ID_COLUMN = "customer_id"

NUMERIC = [
    "tenure_months",
    "monthly_charges",
    "support_tickets_90d",
    "avg_usage_gb",
    "usage_trend_pct",
    "late_payments_12m",
    "num_add_on_services",
]
CATEGORICAL = [
    "contract",
    "internet_service",
    "payment_method",
    "paperless_billing",
    "region",
    "signup_channel",
]
FEATURES = NUMERIC + CATEGORICAL


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _calibrate_intercept(z: np.ndarray, target_rate: float) -> float:
    """Find the intercept so the mean churn probability equals ``target_rate``."""
    lo, hi = -15.0, 15.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _sigmoid(z + mid).mean() < target_rate:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def generate_customers(n: int = 12000, seed: int = 7, target_rate: float = 0.26) -> pd.DataFrame:
    """Return ``n`` synthetic customers with a ``churned`` label."""
    if n < 100:
        raise ValueError("n must be at least 100")
    if not 0.01 < target_rate < 0.99:
        raise ValueError("target_rate must be between 0.01 and 0.99")

    rng = np.random.default_rng(seed)

    contract = rng.choice(["month-to-month", "one-year", "two-year"], size=n, p=[0.55, 0.25, 0.20])
    internet = rng.choice(["fiber", "dsl", "none"], size=n, p=[0.45, 0.40, 0.15])
    region = rng.choice(["north", "south", "east", "west", "central"], size=n)
    channel = rng.choice(["online", "retail store", "partner", "telesales"], size=n, p=[0.40, 0.25, 0.15, 0.20])
    payment = rng.choice(
        ["card autopay", "bank autopay", "electronic check", "mailed check"],
        size=n,
        p=[0.30, 0.25, 0.30, 0.15],
    )
    paperless = rng.choice(["yes", "no"], size=n, p=[0.60, 0.40])

    tenure = np.clip(rng.gamma(shape=2.2, scale=14.0, size=n), 1, 72)
    tenure = np.where(contract == "two-year", np.clip(tenure + rng.integers(6, 24, n), 1, 72), tenure)
    tenure = np.round(tenure).astype(int)

    add_ons = np.clip(rng.poisson(1.4, n), 0, 6)
    add_ons = np.where(internet == "none", 0, add_ons)

    base_price = np.select([internet == "fiber", internet == "dsl"], [78.0, 52.0], default=25.0)
    monthly = np.clip(base_price + 6.0 * add_ons + rng.normal(0, 7, n), 15, 150).round(2)

    ticket_rate = np.where(internet == "fiber", 1.1, 0.8) * (1 + 0.3 * (contract == "month-to-month"))
    tickets = rng.poisson(ticket_rate)

    usage_mu = np.select([internet == "fiber", internet == "dsl"], [5.6, 4.9], default=3.5)
    usage = rng.lognormal(mean=usage_mu, sigma=0.45).round(1)
    trend = (rng.normal(0, 18, n) - 4.0 * tickets).round(1)

    late = rng.poisson(np.where(payment == "electronic check", 0.9, 0.35))

    z = (
        1.00 * (contract == "month-to-month")
        - 0.90 * (contract == "two-year")
        - 0.030 * tenure
        + 0.018 * (monthly - 65)
        + 0.32 * tickets
        - 0.018 * trend
        + 0.22 * late
        + 0.45 * ((internet == "fiber") & (monthly > 85))
        + 0.35 * (payment == "electronic check")
        - 0.20 * np.isin(payment, ["card autopay", "bank autopay"])
        - 0.12 * add_ons
        + 0.15 * (paperless == "yes")
        + 0.25 * (channel == "telesales")
        + rng.normal(0, 0.6, n)
    )
    z = z + _calibrate_intercept(z, target_rate)
    churned = (rng.random(n) < _sigmoid(z)).astype(int)

    frame = pd.DataFrame(
        {
            ID_COLUMN: [f"C{100000 + i}" for i in range(n)],
            "tenure_months": tenure,
            "monthly_charges": monthly,
            "support_tickets_90d": tickets,
            "avg_usage_gb": usage,
            "usage_trend_pct": trend,
            "late_payments_12m": late,
            "num_add_on_services": add_ons,
            "contract": contract,
            "internet_service": internet,
            "payment_method": payment,
            "paperless_billing": paperless,
            "region": region,
            "signup_channel": channel,
            TARGET: churned,
        }
    )

    # Telemetry gaps: usage fields are missing at random for a few customers.
    frame.loc[rng.random(n) < 0.04, "avg_usage_gb"] = np.nan
    frame.loc[rng.random(n) < 0.06, "usage_trend_pct"] = np.nan
    return frame


def split_features_target(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Return the model inputs and target; the id and label are never features."""
    return frame[FEATURES].copy(), frame[TARGET].copy()
