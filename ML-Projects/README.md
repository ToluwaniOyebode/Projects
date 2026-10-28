# Data, AI and ML projects

Three end-to-end projects, each built around a question a hiring manager would ask: *how do you know it works?* Every project is reproducible from one command and one seed, ships its real results and figures, and states its own limitations.

| Project | What it answers | Highlights |
| --- | --- | --- |
| [Churn Intelligence](churn-intelligence/) | Which customers should we call, and is it worth the money? | Model comparison, calibration, break-even decision rule, profit curve, lift and gains |
| [Demand Forecasting Lab](demand-forecasting-lab/) | Is this forecast actually better, and what does it do to stock? | Rolling-origin backtests, leakage tamper test, known-future promotions, prediction intervals |
| [Ticket Triage NLP](ticket-triage-nlp/) | Which tickets can a machine safely handle? | Unseen-phrasing evaluation, confidence routing, typo robustness, similar-ticket search |

## Results at a glance

| Project | Headline | Honest caveat |
| --- | --- | --- |
| Churn | Break-even targeting earns **$70.8k** vs $34.1k for random contact on 3,000 test customers (ROC AUC 0.784) | Logistic regression beat boosting, because the data is mostly additive |
| Forecasting | **39% lower error** than seasonal naive (WAPE 19.2% vs 31.4%); promo-day bias cut from about -29% to -2.6% | The nominal 80% interval covered 76% |
| Ticket triage | **0.97 macro F1 on a random split but 0.62 to 0.69 on unseen phrasings** | Confidence routing missed its 95% accuracy target (90.6%) |

## Shared principles

- **No leakage, and tests to prove it.** Features are built only from data available at prediction time, and the forecasting project overwrites the entire future with junk to confirm nothing changes.
- **Honest evaluation.** Hold out what production would hold out: new customers, future days, unseen wording.
- **Decisions, not just scores.** Probabilities become dollars, forecasts become stock levels, confidence becomes an automate-or-escalate rule.
- **Disagreements are reported, not hidden.** When a metric misses its target or two selection signals disagree, the report says so.

## Run any project

```sh
cd churn-intelligence        # or demand-forecasting-lab, ticket-triage-nlp
pip install -r requirements.txt
python run.py                # regenerates results/ (20 to 40 seconds)
python -m unittest discover -s tests -t .
```

All three use only `numpy`, `pandas` (churn and forecasting), `scikit-learn` and `matplotlib`. No API keys, accounts or downloads are needed, and all data is synthetic and generated locally.

## Note on data and tooling

The datasets are synthetic by design, so the numbers show that the methods work, not how they would perform on real customers, sales or tickets. These projects were built with AI assistance and then verified by running the full test suites (43 tests in total) and every experiment end to end.
