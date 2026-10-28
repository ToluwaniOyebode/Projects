"""Forecasters: two seasonal baselines, damped Holt-Winters and a global boosted model.

Every forecaster receives only the *observed* history ``units[:, :origin + 1]`` plus
the planned calendar (promotions, holidays), and returns a ``Forecast`` for the next
``horizon`` days.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from .data import Panel
from .features import CATEGORICAL_FEATURES, MIN_ORIGIN, build_features


@dataclass
class Forecast:
    mean: np.ndarray  # (S, H)
    lower: np.ndarray | None = None
    upper: np.ndarray | None = None


def _same_weekday_index(origin: int, horizon: int) -> np.ndarray:
    """Index of the most recent observation that shares each target day's weekday."""
    horizons = np.arange(1, horizon + 1)
    return origin + horizons - 7 * np.ceil(horizons / 7.0).astype(int)


class SeasonalNaive:
    name = "Seasonal naive"

    def forecast(self, units: np.ndarray, panel: Panel, horizon: int) -> Forecast:
        origin = units.shape[1] - 1
        return Forecast(mean=units[:, _same_weekday_index(origin, horizon)].astype(float))


class SeasonalAverage:
    name = "4-week seasonal average"

    def __init__(self, weeks: int = 4):
        self.weeks = weeks

    def forecast(self, units: np.ndarray, panel: Panel, horizon: int) -> Forecast:
        origin = units.shape[1] - 1
        base = _same_weekday_index(origin, horizon)
        stacked = np.stack([units[:, base - 7 * j] for j in range(self.weeks)])
        return Forecast(mean=stacked.mean(axis=0))


def _holt_winters_run(y: np.ndarray, alpha: float, beta: float, gamma: float, phi: float, m: int):
    """Additive damped-trend, additive-seasonality exponential smoothing (error-correction form)."""
    level = y[:m].mean()
    trend = (y[m : 2 * m].mean() - y[:m].mean()) / m
    seasonal = list(y[:m] - level)
    sse = 0.0
    for t in range(m, len(y)):
        slot = t % m
        error = y[t] - (level + phi * trend + seasonal[slot])
        sse += error * error
        level = level + phi * trend + alpha * error
        trend = phi * trend + alpha * beta * error
        seasonal[slot] = seasonal[slot] + gamma * (1 - alpha) * error
    return sse, level, trend, seasonal


class HoltWinters:
    name = "Damped Holt-Winters"
    GRID = [(a, b, g) for a in (0.05, 0.1, 0.2, 0.35) for b in (0.02, 0.1) for g in (0.05, 0.15, 0.3)]

    def __init__(self, season: int = 7, phi: float = 0.98, window: int = 364):
        self.season, self.phi, self.window = season, phi, window

    def forecast(self, units: np.ndarray, panel: Panel, horizon: int) -> Forecast:
        origin = units.shape[1] - 1
        predictions = np.zeros((units.shape[0], horizon))
        for s in range(units.shape[0]):
            y = units[s, -self.window :].astype(float)
            n = len(y)
            best = min(
                ((_holt_winters_run(y, a, b, g, self.phi, self.season), (a, b, g)) for a, b, g in self.GRID),
                key=lambda item: item[0][0],
            )
            (_, level, trend, seasonal), _ = best
            for h in range(1, horizon + 1):
                damped = sum(self.phi**i for i in range(1, h + 1)) * trend
                predictions[s, h - 1] = max(level + damped + seasonal[(n - 1 + h) % self.season], 0.0)
        return Forecast(mean=predictions)


class GlobalBoosting:
    """One gradient-boosted model shared by all series, trained directly for horizons 1..H.

    Targets are expressed as a ratio to each series' recent 28-day mean, so series with
    very different volumes can share what they learn about weekdays, promotions and holidays.
    """

    name = "Global gradient boosting"

    def __init__(self, quantiles=(0.1, 0.9), origin_step: int = 3, quick: bool = False, seed: int = 0):
        self.quantiles = quantiles
        self.origin_step = origin_step
        self.quick = quick
        self.seed = seed

    def _regressor(self, **kwargs) -> HistGradientBoostingRegressor:
        return HistGradientBoostingRegressor(
            learning_rate=0.06,
            max_iter=80 if self.quick else 220,
            max_leaf_nodes=15,
            min_samples_leaf=40,
            l2_regularization=1.0,
            categorical_features=CATEGORICAL_FEATURES,
            random_state=self.seed,
            **kwargs,
        )

    def forecast(self, units: np.ndarray, panel: Panel, horizon: int) -> Forecast:
        origin = units.shape[1] - 1
        train_origins = np.arange(MIN_ORIGIN, origin - horizon + 1, self.origin_step)
        X, y, _ = build_features(units, panel, train_origins, horizon, with_target=True)
        X_next, _, scale = build_features(units, panel, [origin], horizon, with_target=False)

        point = self._regressor(loss="poisson").fit(X, y).predict(X_next) * scale
        shape = (units.shape[0], horizon)
        mean = point.reshape(shape)

        lower = upper = None
        if self.quantiles:
            low_q, high_q = self.quantiles
            low = self._regressor(loss="quantile", quantile=low_q).fit(X, y).predict(X_next) * scale
            high = self._regressor(loss="quantile", quantile=high_q).fit(X, y).predict(X_next) * scale
            lower = np.minimum(low.reshape(shape), mean)
            upper = np.maximum(high.reshape(shape), mean)
        return Forecast(mean=mean, lower=lower, upper=upper)
