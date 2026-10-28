"""Matplotlib figures for the churn report (headless, consistent styling)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

INK = "#1f2933"
MUTED = "#8a97a6"
ACCENT = "#2563eb"
WARM = "#e4572e"
GOOD = "#16a34a"
GRID = "#e5e9ef"


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=INK)


def _save(fig, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)
    return path.name


def plot_roc_pr(y_true, curves: dict[str, np.ndarray], out_dir: Path) -> str:
    fig, (ax_roc, ax_pr) = plt.subplots(1, 2, figsize=(11, 4.4))
    colors = [MUTED, WARM, ACCENT, GOOD]
    for color, (name, scores) in zip(colors, curves.items()):
        fpr, tpr, _ = roc_curve(y_true, scores)
        precision, recall, _ = precision_recall_curve(y_true, scores)
        ax_roc.plot(fpr, tpr, color=color, linewidth=2, label=name)
        ax_pr.plot(recall, precision, color=color, linewidth=2, label=name)
    ax_roc.plot([0, 1], [0, 1], color=MUTED, linestyle="--", linewidth=1)
    ax_pr.axhline(np.mean(y_true), color=MUTED, linestyle="--", linewidth=1)
    _style(ax_roc, "ROC curve (held-out test set)", "False positive rate", "True positive rate")
    _style(ax_pr, "Precision-recall curve", "Recall", "Precision")
    ax_roc.legend(frameon=False, loc="lower right")
    return _save(fig, out_dir / "roc_pr.png")


def plot_calibration(y_true, before, after, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(5.6, 5))
    ax.plot([0, 1], [0, 1], color=MUTED, linestyle="--", linewidth=1, label="Perfect calibration")
    for scores, label, color in ((before, "Raw model", WARM), (after, "Isotonic calibrated", ACCENT)):
        frac_pos, mean_pred = calibration_curve(y_true, scores, n_bins=10, strategy="quantile")
        ax.plot(mean_pred, frac_pos, marker="o", color=color, linewidth=2, label=label)
    _style(ax, "Do predicted risks match reality?", "Mean predicted churn probability", "Observed churn rate")
    ax.legend(frameon=False)
    return _save(fig, out_dir / "calibration.png")


def plot_lift(table: list[dict], out_dir: Path) -> str:
    deciles = [row["decile"] for row in table]
    capture = [row["cumulative_capture"] * 100 for row in table]
    rates = [row["churn_rate"] * 100 for row in table]
    fig, (ax_bar, ax_gain) = plt.subplots(1, 2, figsize=(11, 4.4))
    ax_bar.bar(deciles, rates, color=ACCENT)
    ax_bar.axhline(np.mean(rates), color=WARM, linestyle="--", linewidth=1.2)
    _style(ax_bar, "Churn rate by risk decile", "Risk decile (1 = highest risk)", "Churn rate (%)")
    ax_gain.plot([0] + deciles, [0] + capture, marker="o", color=ACCENT, linewidth=2, label="Model")
    ax_gain.plot([0, 10], [0, 100], color=MUTED, linestyle="--", linewidth=1, label="Random targeting")
    _style(ax_gain, "Cumulative gains", "Deciles contacted", "Churners captured (%)")
    ax_gain.legend(frameon=False, loc="lower right")
    return _save(fig, out_dir / "lift_gains.png")


def plot_profit(thresholds, profits, breakeven: float, best: tuple[float, float], out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.plot(thresholds, profits, color=ACCENT, linewidth=2.2)
    ax.axvline(breakeven, color=MUTED, linestyle="--", linewidth=1.2, label=f"Break-even p = {breakeven:.3f}")
    ax.scatter([best[0]], [best[1]], color=WARM, zorder=5, s=55, label=f"Best realised: p >= {best[0]:.3f}")
    ax.axhline(0, color=INK, linewidth=0.8)
    _style(ax, "Campaign profit vs contact threshold", "Contact customers with predicted risk >=", "Profit on test customers ($)")
    ax.legend(frameon=False)
    return _save(fig, out_dir / "profit_curve.png")


def plot_importance(names, means, stds, out_dir: Path) -> str:
    order = np.argsort(means)
    fig, ax = plt.subplots(figsize=(7.4, 5))
    ax.barh(np.array(names)[order], np.array(means)[order], xerr=np.array(stds)[order], color=ACCENT, ecolor=MUTED)
    _style(ax, "Permutation importance (drop in ROC AUC)", "Mean decrease in test ROC AUC", "")
    ax.grid(axis="y", visible=False)
    return _save(fig, out_dir / "feature_importance.png")
