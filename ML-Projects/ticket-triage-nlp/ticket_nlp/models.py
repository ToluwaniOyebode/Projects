"""Text classifiers, grouped splitting and evaluation helpers."""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline

from .data import Ticket

WORD_MODEL = "Word TF-IDF + logistic regression"
CHAR_MODEL = "Word + character TF-IDF + logistic regression"
NB_MODEL = "Word TF-IDF + complement naive Bayes"


def _word_tfidf() -> TfidfVectorizer:
    # Stop words and bare numbers are dropped so n-grams are built from content words; otherwise bigrams
    # such as "pdf also" (a sentence boundary plus the discourse marker "Also,") become "features".
    return TfidfVectorizer(
        ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode",
        stop_words="english", token_pattern=r"(?u)\b[^\W\d_]{2,}\b",
    )


def _char_tfidf() -> TfidfVectorizer:
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True)


def model_zoo(seed: int = 5) -> dict[str, Pipeline]:
    """Three classifiers that all expose class probabilities (needed for routing)."""
    return {
        WORD_MODEL: Pipeline([("tfidf", _word_tfidf()), ("clf", LogisticRegression(C=10, max_iter=3000))]),
        CHAR_MODEL: Pipeline(
            [
                ("tfidf", FeatureUnion([("word", _word_tfidf()), ("char", _char_tfidf())])),
                ("clf", LogisticRegression(C=10, max_iter=3000)),
            ]
        ),
        NB_MODEL: Pipeline([("tfidf", _word_tfidf()), ("clf", ComplementNB(alpha=0.3))]),
    }


def unpack(tickets: list[Ticket]) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Return ``(texts, labels, template_groups)``."""
    return (
        [t.text for t in tickets],
        np.array([t.category for t in tickets]),
        np.array([t.template_id for t in tickets]),
    )


def random_split(tickets: list[Ticket], test_size: float = 0.25, seed: int = 5):
    """Optimistic split: the same phrasings appear in both train and test."""
    train_idx, test_idx = train_test_split(
        np.arange(len(tickets)), test_size=test_size, random_state=seed, stratify=[t.category for t in tickets]
    )
    return train_idx, test_idx


def grouped_split(tickets: list[Ticket], holdout_per_category: int = 2, seed: int = 5):
    """Honest split: held-out phrasings never appear anywhere in the training data.

    ``holdout_per_category`` templates are chosen per category. Test tickets have a held-out
    primary issue. Training tickets contain *no* held-out wording at all, neither as the primary
    issue nor as a secondary distractor sentence; otherwise the model would see the test phrasings
    in training (under the wrong label) and the evaluation would be contaminated.
    """
    rng = np.random.default_rng(seed)
    held_out = set()
    for category in sorted({t.category for t in tickets}):
        templates = sorted({t.template_id for t in tickets if t.category == category})
        chosen = rng.choice(len(templates), size=min(holdout_per_category, len(templates) - 1), replace=False)
        held_out.update(templates[int(i)] for i in chosen)
    train_idx = [i for i, t in enumerate(tickets) if t.template_id not in held_out and t.secondary_template_id not in held_out]
    test_idx = [i for i, t in enumerate(tickets) if t.template_id in held_out]
    return np.array(train_idx), np.array(test_idx)


def score_predictions(y_true, y_pred) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }
