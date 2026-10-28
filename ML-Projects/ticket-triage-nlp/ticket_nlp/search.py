"""Similar-ticket search: TF-IDF cosine similarity, optionally in a latent semantic (LSA) space."""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import Normalizer


class TicketIndex:
    """Find the most similar past tickets for a new one.

    With ``components=None`` this is plain TF-IDF cosine search (exact word overlap).
    With ``components=k`` the vectors are projected to ``k`` latent dimensions with
    truncated SVD (LSA), so different words that appear in similar contexts can match.
    """

    def __init__(self, components: int | None = None, seed: int = 5):
        self.components = components
        self.seed = seed
        self._tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")
        self._svd = None
        self._matrix = None

    def fit(self, texts: list[str]) -> "TicketIndex":
        matrix = self._tfidf.fit_transform(texts)
        if self.components:
            k = min(self.components, matrix.shape[1] - 1, matrix.shape[0] - 1)
            self._svd = TruncatedSVD(n_components=k, random_state=self.seed)
            matrix = Normalizer(copy=False).fit_transform(self._svd.fit_transform(matrix))
        self._matrix = matrix
        return self

    def _encode(self, texts: list[str]):
        matrix = self._tfidf.transform(texts)
        if self._svd is not None:
            matrix = Normalizer(copy=False).fit_transform(self._svd.transform(matrix))
        return matrix

    def search(self, texts: list[str], k: int = 5) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(indices, similarities)`` of the top ``k`` index entries per query, best first."""
        if self._matrix is None:
            raise RuntimeError("fit the index before searching")
        scores = self._encode(texts) @ self._matrix.T
        scores = scores.toarray() if hasattr(scores, "toarray") else np.asarray(scores)
        k = min(k, scores.shape[1])
        top = np.argsort(-scores, axis=1, kind="stable")[:, :k]
        return top, np.take_along_axis(scores, top, axis=1)


def evaluate_retrieval(index: TicketIndex, queries: list[str], query_labels, index_labels, ks=(1, 5)) -> dict[str, float]:
    """Category precision@k and mean reciprocal rank of the first same-category result."""
    query_labels, index_labels = np.asarray(query_labels), np.asarray(index_labels)
    top, _ = index.search(queries, k=max(max(ks), 20))
    relevant = index_labels[top] == query_labels[:, None]
    result = {f"precision_at_{k}": float(relevant[:, :k].mean()) for k in ks}
    first_hit = np.where(relevant.any(axis=1), relevant.argmax(axis=1) + 1, np.inf)
    result["mrr"] = float(np.mean(1.0 / first_hit))
    return result
