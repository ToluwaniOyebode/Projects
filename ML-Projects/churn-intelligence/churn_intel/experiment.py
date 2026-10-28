"""Run the full churn experiment and write metrics, figures and a report."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split

from . import plots
from .business import RetentionEconomics, best_threshold, campaign_profit, lift_table, profit_curve
from .data import CATEGORICAL, FEATURES, NUMERIC, TARGET, generate_customers, split_features_target
from .modeling import evaluate_probabilities, model_zoo
from .report import render_report


def run_experiment(output_dir: str | Path = "results", n: int = 12000, seed: int = 7, quick: bool = False) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    economics = RetentionEconomics()

    frame = generate_customers(n=n, seed=seed)
    X, y = split_features_target(frame)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, stratify=y, random_state=seed)

    # 1. Compare model families with cross-validation on the training split only.
    folds = 3 if quick else 5
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    zoo = model_zoo(seed=seed, quick=quick)
    cv_rows = {}
    for name, pipeline in zoo.items():
        scores = cross_validate(pipeline, X_train, y_train, cv=cv, scoring=["roc_auc", "average_precision"], n_jobs=1)
        cv_rows[name] = {
            "cv_roc_auc_mean": float(scores["test_roc_auc"].mean()),
            "cv_roc_auc_std": float(scores["test_roc_auc"].std()),
            "cv_pr_auc_mean": float(scores["test_average_precision"].mean()),
        }
    best_name = max(cv_rows, key=lambda k: cv_rows[k]["cv_roc_auc_mean"])

    # 2. Fit every model on the full training split and score the untouched test split.
    test_scores, test_metrics = {}, {}
    for name, pipeline in zoo.items():
        fitted = clone(pipeline).fit(X_train, y_train)
        test_scores[name] = fitted.predict_proba(X_test)[:, 1]
        test_metrics[name] = evaluate_probabilities(y_test, test_scores[name])

    # 3. Calibrate the winner so predicted probabilities can be used in money terms.
    calibrated = CalibratedClassifierCV(clone(zoo[best_name]), method="isotonic", cv=5).fit(X_train, y_train)
    calibrated_scores = calibrated.predict_proba(X_test)[:, 1]
    calibrated_metrics = evaluate_probabilities(y_test, calibrated_scores)

    # 4. Business decision: who should receive the retention offer?
    y_test_arr = y_test.to_numpy()
    thresholds, profits = profit_curve(y_test_arr, calibrated_scores, economics)
    best_t, best_profit = best_threshold(y_test_arr, calibrated_scores, economics)
    rule_mask = calibrated_scores >= economics.breakeven_probability
    rng = np.random.default_rng(seed)
    random_mask = rng.random(len(y_test_arr)) < rule_mask.mean()
    strategies = {
        "Contact nobody": 0.0,
        "Contact everyone": campaign_profit(y_test_arr, np.ones(len(y_test_arr), bool), economics),
        "Random, same volume": campaign_profit(y_test_arr, random_mask, economics),
        "Model, break-even rule": campaign_profit(y_test_arr, rule_mask, economics),
        "Model, best threshold (hindsight)": best_profit,
    }

    lift = lift_table(y_test_arr, calibrated_scores)

    # 5. Explain: permutation importance on raw columns, and slice quality by contract.
    importance = permutation_importance(
        calibrated, X_test, y_test, scoring="roc_auc", n_repeats=3 if quick else 6, random_state=seed, n_jobs=1
    )
    ranked = sorted(zip(FEATURES, importance.importances_mean, importance.importances_std), key=lambda r: -r[1])
    segments = {}
    for contract in sorted(X_test["contract"].unique()):
        mask = (X_test["contract"] == contract).to_numpy()
        segments[contract] = {
            "customers": int(mask.sum()),
            "churn_rate": float(y_test_arr[mask].mean()),
            "roc_auc": float(roc_auc_score(y_test_arr[mask], calibrated_scores[mask])),
        }

    figures = [
        plots.plot_roc_pr(y_test_arr, {**test_scores, f"{best_name} (calibrated)": calibrated_scores}, out),
        plots.plot_calibration(y_test_arr, test_scores[best_name], calibrated_scores, out),
        plots.plot_lift(lift, out),
        plots.plot_profit(thresholds, profits, economics.breakeven_probability, (best_t, best_profit), out),
        plots.plot_importance([r[0] for r in ranked], [r[1] for r in ranked], [r[2] for r in ranked], out),
    ]

    results = {
        "dataset": {
            "customers": int(len(frame)),
            "churn_rate": float(frame[TARGET].mean()),
            "numeric_features": NUMERIC,
            "categorical_features": CATEGORICAL,
            "train_size": int(len(X_train)),
            "test_size": int(len(X_test)),
            "seed": seed,
        },
        "cross_validation": cv_rows,
        "selected_model": best_name,
        "test_metrics": test_metrics,
        "calibrated_test_metrics": calibrated_metrics,
        "economics": {
            "contact_cost": economics.contact_cost,
            "save_rate": economics.save_rate,
            "customer_value": economics.customer_value,
            "breakeven_probability": economics.breakeven_probability,
        },
        "campaign_profit_test": strategies,
        "best_threshold": best_t,
        "lift_deciles": lift,
        "feature_importance": [{"feature": f, "mean": float(m), "std": float(s)} for f, m, s in ranked],
        "segments_by_contract": segments,
        "figures": figures,
    }
    (out / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "REPORT.md").write_text(render_report(results), encoding="utf-8")
    return results
