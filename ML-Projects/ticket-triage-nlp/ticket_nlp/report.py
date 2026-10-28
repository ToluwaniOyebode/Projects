"""Render the ticket triage study as Markdown."""

from __future__ import annotations


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _clip(text: str, limit: int = 140) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_report(r: dict) -> str:
    d, models, routing = r["dataset"], r["models"], r["routing"]
    selected = r["selected_model"]
    sel = models[selected]
    best_on_test = max(models, key=lambda k: models[k]["grouped_split"]["macro_f1"])
    lines = [
        "# Ticket Triage NLP: results report",
        "",
        f"{d['tickets']:,} synthetic support tickets across {len(d['categories'])} categories, written from {d['templates']} phrasing templates "
        f"plus greetings, filler, typos and secondary issues. Seed {d['seed']}.",
        "",
        "> The data is generated, so these numbers demonstrate the method rather than real-world performance.",
        "",
        "## 1. Two ways to evaluate",
        "",
        "A **random split** lets the same phrasings appear in training and test, which rewards memorisation. "
        f"The **unseen-phrasing split** holds out whole templates ({d['test_templates']} of {d['templates']}, "
        f"{d['test_tickets']:,} test tickets), so the model must generalise to wording it has never seen. "
        "Model selection used grouped cross-validation on the training portion only.",
        "",
        "| Model | Macro F1, random split | Macro F1, unseen phrasings | Grouped CV macro F1 |",
        "| --- | --- | --- | --- |",
    ]
    for name, m in models.items():
        marker = " **(selected)**" if name == selected else ""
        lines.append(
            f"| {name}{marker} | {m['random_split']['macro_f1']:.3f} | {m['grouped_split']['macro_f1']:.3f} | {m['grouped_cv_macro_f1']:.3f} |"
        )
    gap = sel["random_split"]["macro_f1"] - sel["grouped_split"]["macro_f1"]
    lines += [
        "",
        "Grouped CV is harsher than the final test: its folds hold out one primary template at a time, but that wording can still "
        "appear in the training folds as a *secondary* sentence under another label. It is used only to choose a model, "
        "and the test split is never used for selection. "
        + (
            "Here the test split agrees with that choice."
            if best_on_test == selected
            else f"On this run the test split would have favoured **{best_on_test}** "
            f"({models[best_on_test]['grouped_split']['macro_f1']:.3f} vs {sel['grouped_split']['macro_f1']:.3f}); "
            "that is reported rather than quietly swapped in, because choosing by test score would make the test number optimistic."
        ),
        "",
        f"Selected model accuracy on unseen phrasings: **{_pct(sel['grouped_split']['accuracy'])}**. "
        f"The random split overstated macro F1 by {gap:.3f}.",
        "",
        "![Split comparison](split_comparison.png)",
        "",
        "## 2. Where it goes wrong",
        "",
        "![Confusion matrix](confusion_matrix.png)",
        "",
        "Most frequent mistakes (actual → predicted): "
        + ", ".join(f"{c['actual']} → {c['predicted']} ({c['count']})" for c in r["top_confusions"])
        + ".",
        "",
        f"Accuracy is {_pct(r['accuracy_by_ticket_type']['single_issue'])} for single-issue tickets and "
        f"{_pct(r['accuracy_by_ticket_type']['with_secondary_issue'])} when a second, different issue is mentioned. "
        "The label follows the *primary* issue, so those tickets are legitimately harder.",
        "",
        "Examples of misclassified tickets:",
        "",
    ]
    for example in r["misclassified_examples"]:
        lines.append(
            f"- *\"{_clip(example['text'])}\"* — actual **{example['actual']}**, predicted **{example['predicted']}** "
            f"({example['confidence']:.0%} confident)"
        )
    lines += [
        "",
        "## 3. Safe automation",
        "",
        f"Tickets the model is confident about are routed automatically; the rest go to a person. The confidence threshold was chosen on "
        f"out-of-fold training predictions to hit {r['routing']['target_accuracy']:.0%} accuracy, then applied once to the test set.",
        "",
        "| Threshold | Handled automatically | Accuracy of automated tickets | Escalated to humans |",
        "| --- | --- | --- | --- |",
        f"| {routing['threshold']:.2f} | {_pct(routing['coverage'])} | {_pct(routing['automated_accuracy'])} | {routing['escalated']:,} |",
        "",
        f"Automating every ticket would give {_pct(routing['overall_accuracy_all_automated'])} accuracy. "
        + (
            "The automated accuracy met the target on unseen phrasings."
            if routing["automated_accuracy"] >= routing["target_accuracy"] - 0.005
            else "The automated accuracy fell short of the target on unseen phrasings: confidence learned on training folds is somewhat "
            "optimistic when wording shifts, which is the reason to monitor it in production."
        ),
        "",
        "![Routing trade-off](routing_tradeoff.png)",
        "",
        "## 4. Robustness to typos",
        "",
        "Test tickets were corrupted with extra swapped, dropped and doubled letters. Character n-grams let a model recognise "
        "a misspelled word from its pieces.",
        "",
        "| Typo rate | " + " | ".join(models) + " |",
        "| --- | " + " | ".join("---" for _ in models) + " |",
    ]
    for i, rate in enumerate(r["typo_robustness"]["rates"]):
        lines.append(f"| {rate:.0%} | " + " | ".join(f"{r['typo_robustness']['macro_f1'][name][i]:.3f}" for name in models) + " |")
    lines += [
        "",
        "![Typo robustness](typo_robustness.png)",
        "",
        "## 5. What the model learned",
        "",
        "![Top terms](top_terms.png)",
        "",
        "## 6. Similar-ticket search",
        "",
        "Given a new ticket, retrieve the most similar past tickets. Relevant means same category; queries use unseen phrasings.",
        "",
        "| Method | Precision@1 | Precision@5 | MRR |",
        "| --- | --- | --- | --- |",
    ]
    for name, m in r["retrieval"].items():
        marker = " **(best)**" if name == r["best_search"] else ""
        lines.append(f"| {name}{marker} | {m['precision_at_1']:.3f} | {m['precision_at_5']:.3f} | {m['mrr']:.3f} |")
    lines += ["", "![Retrieval](retrieval.png)", "", f"Sample queries answered by *{r['best_search']}*:", ""]
    for item in r["search_demo"]:
        lines.append(f"**Query ({item['category']}):** {_clip(item['query'], 110)}")
        lines.append("")
        for hit in item["results"]:
            lines.append(f"- `{hit['similarity']:.2f}` [{hit['category']}] {_clip(hit['text'], 110)}")
        lines.append("")
    return "\n".join(lines)
