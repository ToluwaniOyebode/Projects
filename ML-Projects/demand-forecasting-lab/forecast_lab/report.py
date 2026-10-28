"""Render the forecasting benchmark as Markdown."""

from __future__ import annotations


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(r: dict) -> str:
    d, p, models = r["dataset"], r["protocol"], r["models"]
    iv = r["intervals"]
    lines = [
        "# Demand Forecasting Lab: results report",
        "",
        f"{d['series']} synthetic product series, {d['days']:,} days ({d['start']} to {d['end']}), seed {d['seed']}. "
        f"Evaluation: **{p['folds']} rolling-origin folds**, each forecasting {p['horizon_days']} days ahead, "
        f"spaced {p['fold_spacing_days']} days apart ({p['first_test_day']} to {p['last_test_day']}). "
        "Every model only sees data up to the forecast origin.",
        "",
        "> The data is generated, so these numbers demonstrate the method rather than real-world performance.",
        "",
        "![Data overview](data_overview.png)",
        "",
        "## 1. Accuracy",
        "",
        "WAPE is total absolute error divided by total demand, so it stays meaningful on days with very low sales. "
        "MASE below 1 means the model beats a seasonal-naive forecast made in-sample.",
        "",
        "| Model | WAPE | MAE (units) | Bias | MASE |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, m in models.items():
        marker = " **(best)**" if name == r["best_model"] else ""
        lines.append(f"| {name}{marker} | {_pct(m['wape'])} | {m['mae']:.2f} | {m['bias'] * 100:+.1f}% | {m['mase']:.2f} |")
    lines += [
        "",
        f"The boosted model cut error by **{r['improvement_over_naive']:.0%}** relative to the seasonal-naive baseline.",
        "",
        "![Model comparison](model_comparison.png)",
        "",
        "## 2. Error by horizon",
        "",
        "![Horizon error](horizon_error.png)",
        "",
        "## 3. Promotions",
        "",
        "Promotions are planned, so they are known for future dates. Models that cannot use that information "
        "systematically miss the lift; the table shows over/under-forecasting on promotion days.",
        "",
        "| Model | WAPE normal | WAPE promo | Bias normal | Bias promo |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, m in models.items():
        lines.append(
            f"| {name} | {_pct(m['wape_normal'])} | {_pct(m['wape_promo'])} | {m['bias_normal'] * 100:+.1f}% | {m['bias_promo'] * 100:+.1f}% |"
        )
    lines += [
        "",
        "![Promotion effect](promo_effect.png)",
        "",
        "## 4. Uncertainty and inventory",
        "",
        f"The 10th-90th percentile band is meant to cover {iv['nominal_coverage']:.0%} of outcomes; it actually covered "
        f"**{iv['coverage']:.1%}**, with total width equal to {iv['relative_width']:.0%} of demand.",
        "",
        "Stocking decisions compared over the same test days (fill rate = demand served, excess = stock left over):",
        "",
        "| Policy | Fill rate | Excess stock | Stock / demand |",
        "| --- | --- | --- | --- |",
    ]
    for name, m in r["inventory_policies"].items():
        lines.append(f"| {name} | {_pct(m['fill_rate'])} | {_pct(m['excess_stock'])} | {m['stock_to_demand']:.2f} |")
    naive = r["inventory_policies"]["Seasonal naive + 25% buffer"]
    flat = r["inventory_policies"]["Boosting forecast + 25% buffer"]
    quant = r["inventory_policies"]["Boosting 90th percentile"]
    if quant["fill_rate"] - flat["fill_rate"] < 0.01:
        quantile_note = (
            f"The 90th-percentile policy reaches {_pct(quant['fill_rate'])} but holds {quant['stock_to_demand']:.2f}x demand, "
            "so on this data it adds little over a flat buffer on the better forecast; the main value of the quantiles is "
            "the interval itself."
        )
    else:
        quantile_note = (
            f"The 90th-percentile policy lifts fill rate to {_pct(quant['fill_rate'])} while holding {quant['stock_to_demand']:.2f}x demand."
        )
    lines += [
        "",
        f"At a similar stock level ({naive['stock_to_demand']:.2f}x vs {flat['stock_to_demand']:.2f}x demand), the more accurate "
        f"forecast lifts fill rate from {_pct(naive['fill_rate'])} to {_pct(flat['fill_rate'])}. {quantile_note}",
        "",
        "![Forecast grid](forecast_grid.png)",
        "",
    ]
    return "\n".join(lines)
