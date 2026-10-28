"""Run the full ticket triage study and write metrics, figures and a report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score

from . import plots
from .data import CATEGORIES, corrupt_text, generate_tickets
from .models import CHAR_MODEL, WORD_MODEL, grouped_split, model_zoo, random_split, score_predictions, unpack
from .report import render_report
from .routing import apply_threshold, choose_threshold, routing_curve
from .search import TicketIndex, evaluate_retrieval

TYPO_RATES = [0.0, 0.05, 0.10, 0.20]
TARGET_ACCURACY = 0.95


def _top_terms(pipeline, per_class: int = 8) -> dict[str, list[tuple[str, float]]]:
    names = pipeline.named_steps["tfidf"].get_feature_names_out()
    clf = pipeline.named_steps["clf"]
    out = {}
    for row, label in zip(clf.coef_, clf.classes_):
        top = np.argsort(-row)[:per_class]
        out[str(label)] = [(str(names[i]), float(row[i])) for i in top]
    return out


def run_experiment(output_dir: str | Path = "results", n: int = 6000, seed: int = 5, quick: bool = False) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    tickets = generate_tickets(n=n, seed=seed)
    texts, labels, groups = unpack(tickets)
    texts_arr = np.array(texts, dtype=object)
    r_train, r_test = random_split(tickets, seed=seed)
    g_train, g_test = grouped_split(tickets, seed=seed)
    folds = 3 if quick else 5

    # 1. Compare classifiers under an optimistic and an honest evaluation.
    comparison, fitted = {}, {}
    for name, pipeline in model_zoo(seed).items():
        random_model = clone(pipeline).fit(texts_arr[r_train], labels[r_train])
        grouped_model = clone(pipeline).fit(texts_arr[g_train], labels[g_train])
        predictions = grouped_model.predict(texts_arr[g_test])
        cv = cross_val_score(
            clone(pipeline), texts_arr[g_train], labels[g_train], groups=groups[g_train],
            cv=GroupKFold(n_splits=folds), scoring="f1_macro",
        )
        comparison[name] = {
            "random_split": score_predictions(labels[r_test], random_model.predict(texts_arr[r_test])),
            "grouped_split": score_predictions(labels[g_test], predictions),
            "grouped_cv_macro_f1": float(cv.mean()),
        }
        fitted[name] = grouped_model
    selected = max(comparison, key=lambda k: comparison[k]["grouped_cv_macro_f1"])
    model = fitted[selected]
    classes = list(model.classes_)

    # 2. Error analysis on unseen phrasings.
    y_test = labels[g_test]
    proba_test = model.predict_proba(texts_arr[g_test])
    y_pred = np.array(classes)[proba_test.argmax(axis=1)]
    confidence = proba_test.max(axis=1)
    matrix = confusion_matrix(y_test, y_pred, labels=CATEGORIES)
    confusions = Counter(
        (a, p) for a, p in zip(y_test, y_pred) if a != p
    ).most_common(5)
    secondary = np.array([tickets[i].has_secondary_issue for i in g_test])
    secondary_split = {
        "with_secondary_issue": float((y_test[secondary] == y_pred[secondary]).mean()),
        "single_issue": float((y_test[~secondary] == y_pred[~secondary]).mean()),
    }
    wrong = np.where(y_test != y_pred)[0][:4]
    examples = [
        {"text": texts[g_test[i]], "actual": str(y_test[i]), "predicted": str(y_pred[i]), "confidence": float(confidence[i])}
        for i in wrong
    ]

    # 3. Confidence-based routing; the threshold is chosen on out-of-fold training predictions only.
    oof = cross_val_predict(
        clone(model_zoo(seed)[selected]), texts_arr[g_train], labels[g_train], groups=groups[g_train],
        cv=GroupKFold(n_splits=folds), method="predict_proba",
    )
    oof_pred = np.array(classes)[oof.argmax(axis=1)]
    threshold = choose_threshold(labels[g_train], oof_pred, oof.max(axis=1), target_accuracy=TARGET_ACCURACY)
    routing = apply_threshold(y_test, y_pred, confidence, threshold)
    thresholds, coverage, accuracy = routing_curve(y_test, y_pred, confidence)

    # 4. Typo robustness: corrupt the unseen-phrasing test tickets progressively.
    typo_scores = {name: [] for name in comparison}
    for rate in TYPO_RATES:
        rng = np.random.default_rng(seed + int(rate * 100))
        noisy = [corrupt_text(texts[i], rate, rng) for i in g_test]
        for name, fitted_model in fitted.items():
            typo_scores[name].append(score_predictions(y_test, fitted_model.predict(noisy))["macro_f1"])

    # 5. Similar-ticket search against the training tickets.
    rng = np.random.default_rng(seed)
    query_idx = rng.choice(g_test, size=min(600, len(g_test)), replace=False)
    index_texts = [texts[i] for i in g_train]
    retrieval, indexes = {}, {}
    for label, components in (("TF-IDF cosine", None), ("LSA, 50 dimensions", 50), ("LSA, 150 dimensions", 150)):
        index = TicketIndex(components=components, seed=seed).fit(index_texts)
        indexes[label] = index
        retrieval[label] = evaluate_retrieval(index, [texts[i] for i in query_idx], labels[query_idx], labels[g_train])
    best_search = max(retrieval, key=lambda k: retrieval[k]["precision_at_5"])
    demo = []
    for category in CATEGORIES:
        query_i = next((i for i in g_test if labels[i] == category), None)
        if query_i is None:  # this category's phrasings all landed in training
            continue
        top, scores = indexes[best_search].search([texts[query_i]], k=3)
        demo.append(
            {
                "query": texts[query_i],
                "category": category,
                "results": [
                    {"text": index_texts[j], "category": str(labels[g_train][j]), "similarity": float(s)}
                    for j, s in zip(top[0], scores[0])
                ],
            }
        )

    figures = [
        plots.plot_split_comparison(comparison, out),
        plots.plot_confusion(matrix, CATEGORIES, out),
        plots.plot_typo_robustness(TYPO_RATES, typo_scores, out),
        plots.plot_routing(thresholds, coverage, accuracy, routing, out),
        plots.plot_top_terms(_top_terms(fitted[WORD_MODEL]), out),
        plots.plot_retrieval(retrieval, out),
    ]

    results = {
        "dataset": {
            "tickets": len(tickets),
            "categories": CATEGORIES,
            "templates": len(set(groups)),
            "train_tickets": int(len(g_train)),
            "test_tickets": int(len(g_test)),
            "test_templates": len(set(groups[g_test])),
            "seed": seed,
        },
        "models": comparison,
        "selected_model": selected,
        "top_confusions": [{"actual": a, "predicted": p, "count": c} for (a, p), c in confusions],
        "accuracy_by_ticket_type": secondary_split,
        "misclassified_examples": examples,
        "routing": {**routing, "target_accuracy": TARGET_ACCURACY},
        "typo_robustness": {"rates": TYPO_RATES, "macro_f1": typo_scores},
        "retrieval": retrieval,
        "best_search": best_search,
        "search_demo": demo,
        "top_terms": _top_terms(fitted[WORD_MODEL]),
        "figures": figures,
    }
    (out / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "REPORT.md").write_text(render_report(results), encoding="utf-8")
    return results
