"""Leakage-safe feature construction for a direct multi-horizon global model.

For forecast origin ``o`` (the last observed day) and horizon ``h`` the target day
is ``t = o + h``. Every feature that touches *sales* reads index ``<= o`` only.
Promotions and holidays are planned in advance, so they may be read at ``t``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import Panel

CATEGORICAL_FEATURES = ["series", "dow", "holiday_target", "holiday_ref"]
MIN_ORIGIN = 60  # need 56 days of look-back for the trend feature


def _gather(values: np.ndarray, index: np.ndarray) -> np.ndarray:
    """Index a (S, T) array along time; out-of-range positions become NaN."""
    clipped = np.clip(index, 0, values.shape[1] - 1)
    out = np.take_along_axis(values, clipped, axis=1).astype(float)
    out[(index < 0) | (index >= values.shape[1])] = np.nan
    return out


def _nan_mean(stack: np.ndarray) -> np.ndarray:
    """Mean over axis 0 ignoring NaN; positions with no valid value stay NaN (no warnings)."""
    valid = ~np.isnan(stack)
    counts = valid.sum(axis=0)
    totals = np.where(valid, stack, 0.0).sum(axis=0)
    return np.where(counts > 0, totals / np.maximum(counts, 1), np.nan)


def build_features(
    units: np.ndarray,
    panel: Panel,
    origins,
    horizon: int,
    with_target: bool,
) -> tuple[pd.DataFrame, np.ndarray | None, np.ndarray]:
    """Return ``(features, target_ratio, scale)`` stacked over origins, series and horizons.

    ``units`` is the *observed* history, shape (S, n_observed). Passing a truncated
    array makes any accidental peek at the future fail loudly or become NaN.
    """
    n_series, n_observed = units.shape
    horizons = np.arange(1, horizon + 1)
    frames, targets, scales = [], [], []

    for origin in np.atleast_1d(origins):
        origin = int(origin)
        if origin < MIN_ORIGIN or origin > n_observed - 1:
            raise ValueError(f"origin {origin} outside [{MIN_ORIGIN}, {n_observed - 1}]")

        target_idx = np.broadcast_to(origin + horizons, (n_series, horizon))  # (S, H)
        if with_target and origin + horizon > n_observed - 1:
            raise ValueError("target window extends past the observed history")

        recent28 = units[:, origin - 27 : origin + 1].mean(axis=1)
        scale = np.maximum(recent28, 1.0)[:, None]  # (S, 1)
        recent7 = units[:, origin - 6 : origin + 1].mean(axis=1)[:, None]
        previous28 = units[:, origin - 55 : origin - 27].mean(axis=1)[:, None]
        last_value = units[:, origin][:, None]

        weeks_back = np.ceil(horizons / 7.0).astype(int)  # same weekday, most recent week <= origin
        ref1 = np.broadcast_to(origin + horizons - 7 * weeks_back, (n_series, horizon))
        lag1 = _gather(units, ref1)
        lag2 = _gather(units, ref1 - 7)
        lag3 = _gather(units, ref1 - 14)
        lag4 = _gather(units, ref1 - 21)
        same_weekday_mean = _nan_mean(np.stack([lag1, lag2, lag3, lag4]))

        # Same time last year, smoothed over a week to reduce noise (index <= origin for h <= 14).
        year_ref = target_idx - 364
        year_window = np.stack([_gather(units, year_ref + k) for k in range(-3, 4)])
        year_ago = _nan_mean(year_window)

        promo_target = _gather(panel.promo, target_idx)
        promo_ref = _gather(panel.promo, ref1)
        promo_recent = panel.promo[:, origin - 6 : origin + 1].mean(axis=1)[:, None]

        dates = panel.dates[0] + pd.to_timedelta(target_idx.reshape(-1), unit="D")
        doy = dates.dayofyear.to_numpy()
        holiday_target = panel.holiday[np.minimum(target_idx, panel.n_days - 1)]
        holiday_ref = panel.holiday[np.clip(ref1, 0, panel.n_days - 1)]

        shape = (n_series, horizon)
        frame = pd.DataFrame(
            {
                "series": np.repeat(np.arange(n_series), horizon),
                "horizon": np.tile(horizons, n_series),
                "dow": dates.dayofweek.to_numpy(),
                "doy_sin": np.sin(2 * np.pi * doy / 365.25),
                "doy_cos": np.cos(2 * np.pi * doy / 365.25),
                "month": dates.month.to_numpy(),
                "promo_target": promo_target.reshape(-1),
                "promo_ref": promo_ref.reshape(-1),
                "promo_recent": np.broadcast_to(promo_recent, shape).reshape(-1),
                "holiday_target": holiday_target.reshape(-1),
                "holiday_ref": holiday_ref.reshape(-1),
                "last_value": (np.broadcast_to(last_value, shape) / scale).reshape(-1),
                "recent7": (np.broadcast_to(recent7, shape) / scale).reshape(-1),
                "previous28": (np.broadcast_to(previous28, shape) / scale).reshape(-1),
                "lag_wd1": (lag1 / scale).reshape(-1),
                "lag_wd2": (lag2 / scale).reshape(-1),
                "lag_wd3": (lag3 / scale).reshape(-1),
                "same_weekday_mean": (same_weekday_mean / scale).reshape(-1),
                "year_ago": (year_ago / scale).reshape(-1),
            }
        )
        frames.append(frame)
        scales.append(np.broadcast_to(scale, shape).reshape(-1))
        if with_target:
            targets.append((_gather(units, target_idx) / scale).reshape(-1))

    features = pd.concat(frames, ignore_index=True)
    target = np.concatenate(targets) if with_target else None
    return features, target, np.concatenate(scales)
