"""Headless matplotlib figures for the forecasting report."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, MUTED, GRID = "#1f2933", "#8a97a6", "#e5e9ef"
PALETTE = {
    "Seasonal naive": "#8a97a6",
    "4-week seasonal average": "#d99a2b",
    "Damped Holt-Winters": "#e4572e",
    "Global gradient boosting": "#2563eb",
}


def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color=INK)
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=9)


def _save(fig, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)
    return path.name


def plot_data_overview(panel, out_dir: Path) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    for ax, s in zip(axes, (0, 1)):
        y = panel.units[s]
        rolling = np.convolve(y, np.ones(28) / 28, mode="same")
        ax.plot(panel.dates, y, color="#c3cedb", linewidth=0.7, label="Daily units")
        ax.plot(panel.dates, rolling, color="#2563eb", linewidth=2, label="28-day average")
        promo_days = panel.promo[s] == 1
        ax.scatter(panel.dates[promo_days], y[promo_days], color="#e4572e", s=6, zorder=3, label="Promotion day")
        _style(ax, f"{panel.series_ids[s]}: trend, yearly cycle, weekday shape and promotions", ylabel="Units")
        ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=8)
    return _save(fig, out_dir / "data_overview.png")


def plot_model_comparison(summary: dict, out_dir: Path) -> str:
    names = list(summary)
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    for i, name in enumerate(names):
        folds = np.array(summary[name]["fold_wape"]) * 100
        ax.bar(i, summary[name]["wape"] * 100, color=PALETTE.get(name, "#2563eb"), width=0.62)
        ax.scatter(np.full(len(folds), i), folds, color=INK, s=14, zorder=3)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n.replace(" ", "\n", 1) for n in names], fontsize=9)
    _style(ax, "Forecast error by model (lower is better)", ylabel="WAPE, % (dots = individual folds)")
    ax.grid(axis="x", visible=False)
    return _save(fig, out_dir / "model_comparison.png")


def plot_horizon_error(summary: dict, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    for name, item in summary.items():
        horizon_wape = np.array(item["horizon_wape"]) * 100
        ax.plot(range(1, len(horizon_wape) + 1), horizon_wape, marker="o", markersize=4, linewidth=2,
                color=PALETTE.get(name, "#2563eb"), label=name)
    _style(ax, "Error by forecast horizon", "Days ahead", "WAPE (%)")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, out_dir / "horizon_error.png")


def plot_forecast_grid(panel, fold: dict, naive_fold: dict, horizon: int, out_dir: Path) -> str:
    origin = fold["origin"]
    lookback = 42
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.2), sharex=False)
    for s, ax in enumerate(axes.flat[: panel.n_series]):
        hist_idx = np.arange(origin - lookback + 1, origin + 1)
        future_idx = np.arange(origin + 1, origin + 1 + horizon)
        ax.plot(panel.dates[hist_idx], panel.units[s, hist_idx], color="#9aa7b6", linewidth=1.3, label="History")
        ax.plot(panel.dates[future_idx], fold["actual"][s], color=INK, linewidth=1.8, label="Actual")
        ax.plot(panel.dates[future_idx], naive_fold["mean"][s], color=PALETTE["Seasonal naive"], linestyle=":",
                linewidth=1.6, label="Seasonal naive")
        ax.plot(panel.dates[future_idx], fold["mean"][s], color=PALETTE["Global gradient boosting"], linewidth=2,
                label="Boosting forecast")
        if fold["lower"] is not None:
            ax.fill_between(panel.dates[future_idx], fold["lower"][s], fold["upper"][s],
                            color=PALETTE["Global gradient boosting"], alpha=0.18, label="80% interval")
        ax.axvline(panel.dates[origin], color=MUTED, linestyle="--", linewidth=1)
        _style(ax, panel.series_ids[s])
        ax.tick_params(axis="x", rotation=30)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, frameon=False, fontsize=9)
    fig.suptitle("Last backtest fold: 14-day-ahead forecasts against what actually happened", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    path = out_dir / "forecast_grid.png"
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)
    return path.name


def plot_promo_effect(summary: dict, out_dir: Path) -> str:
    names = list(summary)
    x = np.arange(len(names))
    fig, (ax_w, ax_b) = plt.subplots(1, 2, figsize=(12, 4.4))
    for offset, key, label, color in ((-0.2, "wape_normal", "Normal days", "#9aa7b6"), (0.2, "wape_promo", "Promotion days", "#e4572e")):
        ax_w.bar(x + offset, [summary[n][key] * 100 for n in names], width=0.38, color=color, label=label)
    for offset, key, color in ((-0.2, "bias_normal", "#9aa7b6"), (0.2, "bias_promo", "#e4572e")):
        ax_b.bar(x + offset, [summary[n][key] * 100 for n in names], width=0.38, color=color)
    for ax in (ax_w, ax_b):
        ax.set_xticks(x)
        ax.set_xticklabels([n.replace(" ", "\n", 1) for n in names], fontsize=8.5)
    ax_b.axhline(0, color=INK, linewidth=0.8)
    _style(ax_w, "Error on promotion vs normal days", ylabel="WAPE (%)")
    _style(ax_b, "Bias on promotion vs normal days (0 = unbiased)", ylabel="Over / under forecast (%)")
    ax_w.legend(frameon=False)
    return _save(fig, out_dir / "promo_effect.png")
