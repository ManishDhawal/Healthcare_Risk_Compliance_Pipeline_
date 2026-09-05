import numpy as np
import pandas as pd

from src.models.evaluate import (
    average_precision,
    lift_at_k,
    per_type_recall,
    precision_at_k,
    recall_at_k,
)


def test_perfect_ranking_scores_one():
    y = np.array([1, 1, 0, 0, 0], dtype=bool)
    s = np.array([0.9, 0.8, 0.3, 0.2, 0.1])
    assert precision_at_k(y, s, 2) == 1.0
    assert recall_at_k(y, s, 2) == 1.0
    assert average_precision(y, s) == 1.0


def test_worst_ranking_scores_zero_at_k():
    y = np.array([1, 1, 0, 0, 0], dtype=bool)
    s = np.array([0.1, 0.2, 0.9, 0.8, 0.7])
    assert precision_at_k(y, s, 2) == 0.0
    assert recall_at_k(y, s, 2) == 0.0


def test_lift_of_one_means_no_better_than_random():
    y = np.array([1, 0, 1, 0], dtype=bool)
    s = np.array([1.0, 0.9, 0.8, 0.7])
    # top 2 holds one of two anomalies -> precision 0.5, base rate 0.5
    assert lift_at_k(y, s, 2) == 1.0


def test_k_larger_than_the_dataset_is_clamped():
    y = np.array([1, 0, 0], dtype=bool)
    s = np.array([0.5, 0.4, 0.3])
    assert recall_at_k(y, s, 99) == 1.0


def test_no_anomalies_returns_zero_rather_than_dividing_by_zero():
    y = np.zeros(5, dtype=bool)
    s = np.arange(5, dtype=float)
    assert average_precision(y, s) == 0.0
    assert recall_at_k(y, s, 3) == 0.0
    assert lift_at_k(y, s, 3) == 0.0


def test_per_type_recall_splits_by_label():
    kinds = pd.Series(["", "a", "b", "a", ""])
    s = np.array([0.1, 0.9, 0.8, 0.2, 0.0])
    out = per_type_recall(kinds, s, k=2).set_index("anomaly_type")
    assert out.loc["a", "recall"] == 0.5
    assert out.loc["b", "recall"] == 1.0
