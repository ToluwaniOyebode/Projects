"""Synthetic daily retail demand for several products.

Each series has its own level, growth, weekday shape, yearly seasonality,
promotion response, holiday effects, count noise and occasional stock-outs.
Promotions and holidays are *planned*, so they are known for future dates;
sales are not.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HOLIDAY_NAMES = {
    0: "none",
    1: "New Year's Day",
    2: "Valentine's Day",
    3: "Black Friday",
    4: "Christmas Eve",
    5: "Christmas Day",
    6: "New Year's Eve",
}
_HOLIDAY_EFFECT = {0: 1.0, 1: 0.55, 2: 1.2, 3: 1.35, 4: 1.3, 5: 0.45, 6: 1.15}


@dataclass(frozen=True)
class Panel:
    """A balanced panel: ``units[s, t]`` for series ``s`` on ``dates[t]``."""

    dates: pd.DatetimeIndex
    series_ids: list
    units: np.ndarray  # (S, T) observed sales
    promo: np.ndarray  # (S, T) 1 on promoted days (planned, known ahead)
    holiday: np.ndarray  # (T,) holiday code, 0 = none (known ahead)

    @property
    def n_series(self) -> int:
        return self.units.shape[0]

    @property
    def n_days(self) -> int:
        return self.units.shape[1]

    def to_frame(self) -> pd.DataFrame:
        records = []
        for s, series_id in enumerate(self.series_ids):
            records.append(
                pd.DataFrame(
                    {
                        "date": self.dates,
                        "series_id": series_id,
                        "units": self.units[s],
                        "promo": self.promo[s],
                        "holiday": self.holiday,
                    }
                )
            )
        return pd.concat(records, ignore_index=True)


def holiday_codes(dates: pd.DatetimeIndex) -> np.ndarray:
    """Integer holiday code per date (see ``HOLIDAY_NAMES``)."""
    dates = pd.DatetimeIndex(dates)
    month_day = dates.month * 100 + dates.day
    codes = np.zeros(len(dates), dtype=int)
    codes[month_day == 101] = 1
    codes[month_day == 214] = 2
    codes[month_day == 1224] = 4
    codes[month_day == 1225] = 5
    codes[month_day == 1231] = 6
    for year in sorted(set(dates.year)):
        thursdays = pd.date_range(f"{year}-11-01", f"{year}-11-30", freq="W-THU")
        black_friday = thursdays[3] + pd.Timedelta(days=1)
        codes[dates == black_friday] = 3
    return codes


def _promo_schedule(rng: np.random.Generator, n_days: int) -> np.ndarray:
    promo = np.zeros(n_days, dtype=int)
    day = 0
    while day < n_days:
        if rng.random() < 0.028:
            length = int(rng.integers(3, 8))
            promo[day : day + length] = 1
            day += length + 5  # always a gap between campaigns
        else:
            day += 1
    return promo


def generate_panel(n_series: int = 6, days: int = 1461, seed: int = 11, start: str = "2022-01-01") -> Panel:
    """Generate a reproducible demand panel."""
    if n_series < 1:
        raise ValueError("n_series must be at least 1")
    if days < 400:
        raise ValueError("days must be at least 400 so a full year of history exists")

    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=days, freq="D")
    t = np.arange(days)
    dow = dates.dayofweek.to_numpy()
    doy = dates.dayofyear.to_numpy()
    holidays = holiday_codes(dates)
    holiday_multiplier = np.array([_HOLIDAY_EFFECT[int(code)] for code in holidays])

    weekday_shape = np.array([0.85, 0.85, 0.90, 0.95, 1.10, 1.35, 1.25])
    units = np.zeros((n_series, days))
    promo = np.zeros((n_series, days), dtype=int)

    for s in range(n_series):
        level = rng.uniform(25, 110)
        growth = rng.uniform(-0.05, 0.25)
        weekly = weekday_shape * rng.normal(1.0, 0.06, 7)
        weekly = weekly / weekly.mean()
        amplitude, phase = rng.uniform(0.10, 0.30), rng.uniform(0, 365)
        yearly = 1 + amplitude * np.sin(2 * np.pi * (doy - phase) / 365.25) + 0.05 * np.cos(4 * np.pi * doy / 365.25)
        uplift = rng.uniform(0.35, 0.70)
        promo[s] = _promo_schedule(rng, days)

        mean = level * (1 + growth) ** (t / 365.0) * weekly[dow] * yearly * (1 + uplift * promo[s]) * holiday_multiplier
        dispersion = 30.0
        sales = rng.negative_binomial(dispersion, dispersion / (dispersion + mean)).astype(float)

        # Rare two-day stock-outs: demand happened but nothing was recorded.
        day = 0
        while day < days:
            if rng.random() < 0.003:
                sales[day : day + 2] = 0
                day += 2
            else:
                day += 1
        units[s] = sales

    return Panel(
        dates=dates,
        series_ids=[f"SKU-{i + 1:02d}" for i in range(n_series)],
        units=units,
        promo=promo,
        holiday=holidays,
    )
