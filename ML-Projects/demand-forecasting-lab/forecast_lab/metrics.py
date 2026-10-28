"""Forecast accuracy and inventory-impact metrics."""

from __future__ import annotations

import numpy as np


def mae(actual, forecast) -> float:
    return float(np.mean(np.abs(np.asarray(actual, float) - np.asarray(forecast, float))))


def wape(actual, forecast) -> float:
    """Weighted absolute percentage error: sum|error| / sum(actual). Safe when some actuals are zero."""
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    total = actual.sum()
    return float(np.abs(actual - forecast).sum() / total) if total > 0 else float("nan")


def bias(actual, forecast) -> float:
    """Signed error as a share of demand: positive means over-forecasting."""
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    total = actual.sum()
    return float((forecast - actual).sum() / total) if total > 0 else float("nan")


def mase(actual, forecast, history, season: int = 7) -> float:
    """Mean absolute scaled error against the in-sample seasonal-naive forecast, averaged over series."""
    actual, forecast, history = (np.asarray(a, float) for a in (actual, forecast, history))
    scale = np.mean(np.abs(history[:, season:] - history[:, :-season]), axis=1)
    errors = np.mean(np.abs(actual - forecast), axis=1)
    return float(np.mean(errors / np.maximum(scale, 1e-9)))


def interval_coverage(actual, lower, upper) -> float:
    actual = np.asarray(actual, float)
    return float(np.mean((actual >= np.asarray(lower, float)) & (actual <= np.asarray(upper, float))))


def relative_interval_width(actual, lower, upper) -> float:
    return float(np.sum(np.asarray(upper, float) - np.asarray(lower, float)) / np.sum(np.asarray(actual, float)))


def service_metrics(actual, stock) -> dict[str, float]:
    """Fill rate (share of demand served) and excess stock (share of demand left over)."""
    actual, stock = np.asarray(actual, float), np.asarray(stock, float)
    total = actual.sum()
    return {
        "fill_rate": float(np.minimum(actual, stock).sum() / total),
        "excess_stock": float(np.maximum(stock - actual, 0).sum() / total),
    }
