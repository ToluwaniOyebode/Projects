"""Headless matplotlib figures for the ticket triage report."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, MUTED, GRID = "#1f2933", "#8a97a6", "#e5e9ef"
BLUE, ORANGE, GREEN, GREY = "#2563eb", "#e4572e", "#16a34a", "#9aa7b6"


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


def plot_confusion(matrix: np.ndarray, labels: list[str], out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    normalised = matrix / matrix.sum(axis=1, keepdims=True)
    image = ax.imshow(normalised, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{normalised[i, j]:.0%}", ha="center", va="center", fontsize=9,
                    color="white" if normalised[i, j] > 0.55 else INK)
    ax.set_title("Where tickets get confused (unseen phrasings)", loc="left", fontsize=11.5, fontweight="bold", color=INK)
    ax.set_xlabel("Predicted", color=INK)
    ax.set_ylabel("Actual", color=INK)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    return _save(fig, out_dir / "confusion_matrix.png")


def plot_split_comparison(models: dict, out_dir: Path) -> str:
    names = list(models)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(x - 0.2, [models[n]["random_split"]["macro_f1"] for n in names], 0.38, color=GREY, label="Random split (phrasings seen in training)")
    ax.bar(x + 0.2, [models[n]["grouped_split"]["macro_f1"] for n in names], 0.38, color=BLUE, label="Unseen-phrasing split")
    ax.set_xticks(x)
    ax.set_xticklabels([n.replace(" + ", "\n+ ", 1) for n in names], fontsize=8.5)
    ax.set_ylim(0, 1.05)
    _style(ax, "A random split flatters the models", ylabel="Macro F1")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    return _save(fig, out_dir / "split_comparison.png")


def plot_typo_robustness(rates, scores: dict, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    colors = [GREY, BLUE, ORANGE, GREEN]
    for color, (name, values) in zip(colors, scores.items()):
        ax.plot(np.array(rates) * 100, values, marker="o", linewidth=2, color=color, label=name)
    _style(ax, "Robustness to typos in incoming tickets", "Share of words with a typo (%)", "Macro F1 on unseen phrasings")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, out_dir / "typo_robustness.png")


def plot_routing(thresholds, coverage, accuracy, chosen: dict, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.plot(coverage * 100, accuracy * 100, color=BLUE, linewidth=2.2, label="Test set, sweeping the threshold")
    ax.scatter([chosen["coverage"] * 100], [chosen["automated_accuracy"] * 100], color=ORANGE, s=70, zorder=5,
               label=f"Chosen threshold {chosen['threshold']:.2f} (picked on training folds)")
    _style(ax, "Automate more, or be more accurate?", "Tickets handled automatically (%)", "Accuracy of automated tickets (%)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    return _save(fig, out_dir / "routing_tradeoff.png")


def plot_top_terms(top_terms: dict[str, list[tuple[str, float]]], out_dir: Path) -> str:
    labels = list(top_terms)
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6))
    for ax, label in zip(axes.flat, labels):
        terms = top_terms[label][::-1]
        ax.barh([t for t, _ in terms], [w for _, w in terms], color=BLUE)
        _style(ax, label.replace("_", " "))
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=8.5)
    fig.suptitle("Highest-weight words and phrases per category", x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    path = out_dir / "top_terms.png"
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)
    return path.name


def plot_retrieval(retrieval: dict, out_dir: Path) -> str:
    names = list(retrieval)
    metrics = [("precision_at_1", "Precision@1"), ("precision_at_5", "Precision@5"), ("mrr", "MRR")]
    x = np.arange(len(metrics))
    width = 0.8 / len(names)
    colors = [GREY, BLUE, GREEN, ORANGE]
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    for i, (name, color) in enumerate(zip(names, colors)):
        ax.bar(x + (i - (len(names) - 1) / 2) * width, [retrieval[name][key] for key, _ in metrics], width, color=color, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in metrics])
    ax.set_ylim(0, 1.05)
    _style(ax, "Finding same-category tickets for unseen phrasings", ylabel="Score")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    return _save(fig, out_dir / "retrieval.png")
