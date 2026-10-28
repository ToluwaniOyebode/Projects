"""Rolling-origin evaluation: forecast, reveal the truth, move the origin forward."""

from __future__ import annotations

import numpy as np

from .data import Panel


def rolling_origins(n_days: int, horizon: int, folds: int, step: int = 28) -> list[int]:
    """Last observed index of each fold, oldest first, with non-overlapping test windows."""
    if step < horizon:
        raise ValueError("step must be at least the horizon so test windows do not overlap")
    last = n_days - 1 - horizon
    origins = [last - step * k for k in range(folds)][::-1]
    if origins[0] < 400:
        raise ValueError("not enough history for that many folds")
    return origins


def run_backtest(panel: Panel, models, horizon: int, origins: list[int]) -> dict:
    """Return ``{model: [ {origin, actual, mean, lower, upper}, ... ]}`` per fold."""
    results = {model.name: [] for model in models}
    for origin in origins:
        history = panel.units[:, : origin + 1]  # models never see anything after the origin
        actual = panel.units[:, origin + 1 : origin + 1 + horizon]
        for model in models:
            forecast = model.forecast(history, panel, horizon)
            results[model.name].append(
                {
                    "origin": origin,
                    "actual": actual,
                    "mean": forecast.mean,
                    "lower": forecast.lower,
                    "upper": forecast.upper,
                }
            )
    return results
