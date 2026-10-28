"""Render the experiment results as a readable Markdown report."""

from __future__ import annotations


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def render_report(r: dict) -> str:
    d, eco = r["dataset"], r["economics"]
    selected = r["selected_model"]
    cal = r["calibrated_test_metrics"]
    raw = r["test_metrics"][selected]
    profits = r["campaign_profit_test"]
    top_decile = r["lift_deciles"][0]
    top_three = r["lift_deciles"][2]

    lines = [
        "# Churn Intelligence: results report",
        "",
        f"Synthetic subscription business, {d['customers']:,} customers, base churn rate {d['churn_rate']:.1%}. "
        f"Stratified split: {d['train_size']:,} train / {d['test_size']:,} held-out test. Seed {d['seed']}.",
        "",
        "> The data is generated, so these numbers demonstrate the method rather than real-world performance.",
        "",
        "## 1. Model comparison",
        "",
        f"Cross-validated on the training split only. **{selected}** won on ROC AUC and was carried forward.",
        "",
        "| Model | CV ROC AUC | CV PR AUC | Test ROC AUC | Test PR AUC | Test Brier |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, cv in r["cross_validation"].items():
        t = r["test_metrics"][name]
        lines.append(
            f"| {name} | {cv['cv_roc_auc_mean']:.3f} ± {cv['cv_roc_auc_std']:.3f} | {cv['cv_pr_auc_mean']:.3f} "
            f"| {t['roc_auc']:.3f} | {t['pr_auc']:.3f} | {t['brier']:.3f} |"
        )
    lines += [
        "",
        "![ROC and PR](roc_pr.png)",
        "",
        "## 2. Calibration",
        "",
        "Ranking customers is not enough: the campaign maths needs probabilities that mean what they say.",
        f"Expected calibration error was **{raw['ece']:.3f}** before and **{cal['ece']:.3f}** after isotonic "
        f"calibration (Brier {raw['brier']:.3f} to {cal['brier']:.3f}). "
        + (
            "Calibration improved the probabilities, so the calibrated model is used for decisions."
            if cal["ece"] < raw["ece"] - 0.002
            else "The selected model was already well calibrated, so calibration changed little; "
            "that is expected for regularised logistic regression and is why the check is worth running."
        ),
        "",
        "![Calibration](calibration.png)",
        "",
        "## 3. Where the churners are",
        "",
        f"The riskiest decile churns at {top_decile['churn_rate']:.1%} ({top_decile['lift']:.1f}x the base rate). "
        f"Contacting the top 30% reaches {top_three['cumulative_capture']:.0%} of all churners.",
        "",
        "![Lift and gains](lift_gains.png)",
        "",
        "## 4. Business decision",
        "",
        f"Assumptions: an offer costs {_money(eco['contact_cost'])}, saves {eco['save_rate']:.0%} of would-be churners, "
        f"and each saved customer is worth {_money(eco['customer_value'])}. "
        f"Contact a customer when predicted risk exceeds the break-even probability of **{eco['breakeven_probability']:.3f}**.",
        "",
        "| Strategy | Profit on test customers |",
        "| --- | --- |",
    ]
    for name, value in profits.items():
        lines.append(f"| {name} | {_money(value)} |")
    lines += [
        "",
        "The break-even rule is set before looking at the test labels, so it is an honest estimate. "
        "The hindsight threshold is shown only as an upper bound.",
        "",
        "![Profit curve](profit_curve.png)",
        "",
        "## 5. What drives churn",
        "",
        "| Rank | Feature | Mean AUC drop when shuffled |",
        "| --- | --- | --- |",
    ]
    for rank, item in enumerate(r["feature_importance"][:8], start=1):
        lines.append(f"| {rank} | {item['feature']} | {item['mean']:.4f} |")
    lines += [
        "",
        "![Permutation importance](feature_importance.png)",
        "",
        "## 6. Is it equally good for every contract type?",
        "",
        "| Contract | Customers | Churn rate | ROC AUC |",
        "| --- | --- | --- | --- |",
    ]
    for name, seg in r["segments_by_contract"].items():
        lines.append(f"| {name} | {seg['customers']:,} | {seg['churn_rate']:.1%} | {seg['roc_auc']:.3f} |")
    lines += [
        "",
        "Lower AUC inside a segment is expected because the contract type itself carried much of the signal; "
        "the useful check is that no segment collapses toward 0.5.",
        "",
    ]
    return "\n".join(lines)
