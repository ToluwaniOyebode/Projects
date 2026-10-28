"""Run the full forecasting benchmark and write metrics, figures and a report."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import metrics, plots
from .backtest import rolling_origins, run_backtest
from .data import generate_panel
from .models import GlobalBoosting, HoltWinters, SeasonalAverage, SeasonalNaive
from .report import render_report

BOOSTING = GlobalBoosting.name
NAIVE = SeasonalNaive.name


def _summarise(panel, folds: list[dict], horizon: int) -> dict:
    actual = np.concatenate([f["actual"] for f in folds], axis=1)
    mean = np.concatenate([f["mean"] for f in folds], axis=1)
    promo = np.concatenate([panel.promo[:, f["origin"] + 1 : f["origin"] + 1 + horizon] for f in folds], axis=1) == 1
    return {
        "wape": metrics.wape(actual, mean),
        "mae": metrics.mae(actual, mean),
        "bias": metrics.bias(actual, mean),
        "mase": float(np.mean([metrics.mase(f["actual"], f["mean"], panel.units[:, : f["origin"] + 1]) for f in folds])),
        "fold_wape": [metrics.wape(f["actual"], f["mean"]) for f in folds],
        "horizon_wape": [metrics.wape(actual[:, h::horizon], mean[:, h::horizon]) for h in range(horizon)],
        "wape_promo": metrics.wape(actual[promo], mean[promo]),
        "wape_normal": metrics.wape(actual[~promo], mean[~promo]),
        "bias_promo": metrics.bias(actual[promo], mean[promo]),
        "bias_normal": metrics.bias(actual[~promo], mean[~promo]),
    }


def run_experiment(output_dir: str | Path = "results", folds: int = 8, horizon: int = 14, seed: int = 11, quick: bool = False) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    panel = generate_panel(seed=seed)
    models = [SeasonalNaive(), SeasonalAverage(), HoltWinters(), GlobalBoosting(quick=quick, seed=seed)]
    origins = rolling_origins(panel.n_days, horizon, folds)
    raw = run_backtest(panel, models, horizon, origins)

    summary = {name: _summarise(panel, fold_list, horizon) for name, fold_list in raw.items()}
    best = min(summary, key=lambda name: summary[name]["wape"])
    improvement = 1 - summary[BOOSTING]["wape"] / summary[NAIVE]["wape"]

    boosting = raw[BOOSTING]
    actual = np.concatenate([f["actual"] for f in boosting], axis=1)
    lower = np.concatenate([f["lower"] for f in boosting], axis=1)
    upper = np.concatenate([f["upper"] for f in boosting], axis=1)
    mean = np.concatenate([f["mean"] for f in boosting], axis=1)
    naive_mean = np.concatenate([f["mean"] for f in raw[NAIVE]], axis=1)
    intervals = {
        "nominal_coverage": 0.8,
        "coverage": metrics.interval_coverage(actual, lower, upper),
        "relative_width": metrics.relative_interval_width(actual, lower, upper),
    }

    policies = {
        "Seasonal naive + 25% buffer": naive_mean * 1.25,
        "Boosting forecast + 25% buffer": mean * 1.25,
        "Boosting 90th percentile": upper,
    }
    inventory = {}
    for name, stock in policies.items():
        inventory[name] = {**metrics.service_metrics(actual, stock), "stock_to_demand": float(stock.sum() / actual.sum())}

    figures = [
        plots.plot_data_overview(panel, out),
        plots.plot_model_comparison(summary, out),
        plots.plot_horizon_error(summary, out),
        plots.plot_forecast_grid(panel, boosting[-1], raw[NAIVE][-1], horizon, out),
        plots.plot_promo_effect(summary, out),
    ]

    results = {
        "dataset": {
            "series": panel.n_series,
            "days": panel.n_days,
            "start": str(panel.dates[0].date()),
            "end": str(panel.dates[-1].date()),
            "seed": seed,
        },
        "protocol": {
            "horizon_days": horizon,
            "folds": folds,
            "fold_spacing_days": 28,
            "first_test_day": str(panel.dates[origins[0] + 1].date()),
            "last_test_day": str(panel.dates[origins[-1] + horizon].date()),
        },
        "models": summary,
        "best_model": best,
        "improvement_over_naive": improvement,
        "intervals": intervals,
        "inventory_policies": inventory,
        "figures": figures,
    }
    (out / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "REPORT.md").write_text(render_report(results), encoding="utf-8")
    return results
