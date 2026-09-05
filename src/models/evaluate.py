"""Ranking metrics for the anomaly detector.

The detector produces an ordering, not a decision, so it is scored the way
a review queue is actually used: if an analyst works the top k records,
how many of them are real problems, and how much of the problem set did
they reach?
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Share of the top-k highest-scoring records that are true anomalies."""
    if k <= 0:
        raise ValueError("k must be positive")
    k = min(k, len(scores))
    top = np.argsort(-scores, kind="stable")[:k]
    return float(y_true[top].mean())


def recall_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Share of all true anomalies that appear in the top k."""
    if k <= 0:
        raise ValueError("k must be positive")
    total = int(y_true.sum())
    if total == 0:
        return 0.0
    k = min(k, len(scores))
    top = np.argsort(-scores, kind="stable")[:k]
    return float(y_true[top].sum() / total)


def lift_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Precision@k relative to the base rate.

    Lift of 1.0 means the ranking is no better than picking rows at random.
    """
    base_rate = float(y_true.mean())
    if base_rate == 0:
        return 0.0
    return precision_at_k(y_true, scores, k) / base_rate


def average_precision(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Area under the precision-recall curve, computed over the full ranking."""
    order = np.argsort(-scores, kind="stable")
    hits = y_true[order].astype(float)
    total = hits.sum()
    if total == 0:
        return 0.0
    cum_hits = np.cumsum(hits)
    precision = cum_hits / np.arange(1, len(hits) + 1)
    return float((precision * hits).sum() / total)


def per_type_recall(
    anomaly_type: pd.Series, scores: np.ndarray, k: int
) -> pd.DataFrame:
    """Recall@k broken out by failure mode.

    A single headline number hides the useful part: some failure modes are
    trivially separable in feature space and others are not.
    """
    k = min(k, len(scores))
    top = set(np.argsort(-scores, kind="stable")[:k].tolist())
    labels = anomaly_type.reset_index(drop=True)

    rows = []
    for kind in sorted(x for x in labels.unique() if x):
        idx = set(labels.index[labels == kind].tolist())
        caught = len(idx & top)
        rows.append(
            {
                "anomaly_type": kind,
                "injected": len(idx),
                "caught_at_k": caught,
                "recall": caught / len(idx) if idx else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("recall", ascending=False)


def summarise(
    y_true: np.ndarray,
    scores: np.ndarray,
    anomaly_type: pd.Series,
    ks: tuple[int, ...] = (100, 500, 1000),
) -> dict:
    """Full evaluation payload, ready to serialise."""
    y_true = np.asarray(y_true).astype(bool)
    scores = np.asarray(scores, dtype=float)

    at_k = {
        str(k): {
            "precision": round(precision_at_k(y_true, scores, k), 4),
            "recall": round(recall_at_k(y_true, scores, k), 4),
            "lift": round(lift_at_k(y_true, scores, k), 2),
        }
        for k in ks
    }

    return {
        "n_rows": int(len(y_true)),
        "n_anomalies_injected": int(y_true.sum()),
        "base_rate": round(float(y_true.mean()), 5),
        "average_precision": round(average_precision(y_true, scores), 4),
        "at_k": at_k,
        "per_type_recall_at_1000": per_type_recall(
            anomaly_type, scores, 1000
        ).to_dict(orient="records"),
    }
