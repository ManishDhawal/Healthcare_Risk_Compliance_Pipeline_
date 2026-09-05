"""Manufacture ground truth for the anomaly detector.

The source dataset is synthetic and ships no labels, so an unsupervised
detector fitted on it cannot be evaluated -- there is nothing to check a
ranking against. This module creates that check: it appends copies of real
admission records that have been mutated into specific, domain-motivated
failure modes, and labels them.

The benchmark answers one narrow question: does the detector rank *these
known failure modes* above ordinary records? It does not show that the
detector finds failure modes nobody anticipated. That distinction is the
whole point of reporting it this way, and it is repeated in the README.

Each failure mode below corresponds to something a healthcare revenue
integrity or compliance review would actually flag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Column names as they exist after dbt staging (snake_case).
ADMIT = "date_of_admission"
DISCHARGE = "discharge_date"
BILLING = "billing_amount"
AGE = "age"
CONDITION = "medical_condition"
ADMISSION_TYPE = "admission_type"

ANOMALY_TYPES = (
    "negative_los",
    "extreme_los",
    "billing_high_outlier",
    "billing_negative",
    "short_stay_high_bill",
)


def _as_datetime(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[ADMIT] = pd.to_datetime(out[ADMIT], errors="coerce")
    out[DISCHARGE] = pd.to_datetime(out[DISCHARGE], errors="coerce")
    return out


def inject(
    df: pd.DataFrame,
    rate: float = 0.01,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Append labelled anomalies to ``df``.

    Parameters
    ----------
    df
        Staged admissions, one row per admission.
    rate
        Fraction of the original row count to add as anomalies. 0.01 on
        55,500 rows yields 555 injected records, ~0.99% of the result.
    seed
        Reproducibility.

    Returns
    -------
    combined
        Original rows followed by injected rows, index reset.
    is_anomaly
        Boolean ground truth aligned to ``combined``.
    anomaly_type
        Failure-mode label; empty string for original rows.
    """
    if not 0 < rate < 1:
        raise ValueError(f"rate must be in (0, 1), got {rate}")

    rng = np.random.default_rng(seed)
    base = _as_datetime(df).reset_index(drop=True)

    n_total = int(round(len(base) * rate))
    if n_total < len(ANOMALY_TYPES):
        raise ValueError(
            f"rate {rate} yields only {n_total} anomalies; need at least "
            f"{len(ANOMALY_TYPES)} so every failure mode is represented"
        )

    # Split the budget as evenly as possible across failure modes.
    per_type = np.full(len(ANOMALY_TYPES), n_total // len(ANOMALY_TYPES))
    per_type[: n_total % len(ANOMALY_TYPES)] += 1

    # Billing reference points, computed on the clean data only.
    median_by_condition = base.groupby(CONDITION)[BILLING].median()
    billing_p95 = base[BILLING].quantile(0.95)

    parts: list[pd.DataFrame] = []
    labels: list[str] = []

    for kind, count in zip(ANOMALY_TYPES, per_type):
        rows = base.sample(n=int(count), random_state=rng.integers(0, 2**31)).copy()

        if kind == "negative_los":
            # Discharge recorded before admission -- a straightforward
            # data-integrity failure that should never survive intake.
            shift = rng.integers(1, 30, size=len(rows))
            rows[DISCHARGE] = rows[ADMIT] - pd.to_timedelta(shift, unit="D")

        elif kind == "extreme_los":
            # Stays past a year: usually an unclosed episode rather than a
            # real admission, and they distort every length-of-stay metric.
            stay = rng.integers(400, 1200, size=len(rows))
            rows[DISCHARGE] = rows[ADMIT] + pd.to_timedelta(stay, unit="D")

        elif kind == "billing_high_outlier":
            # Charges far above the norm for the same condition.
            factor = rng.uniform(12, 30, size=len(rows))
            rows[BILLING] = rows[CONDITION].map(median_by_condition).to_numpy() * factor

        elif kind == "billing_negative":
            # Large negative charges. Small negatives occur naturally in
            # this dataset (see README), so injected ones are pushed well
            # outside that range to stay distinguishable.
            rows[BILLING] = -rng.uniform(20_000, 80_000, size=len(rows))

        elif kind == "short_stay_high_bill":
            # A one-day elective stay billed like a major episode: the
            # classic shape of an upcoding or miskeyed-charge review item.
            rows[DISCHARGE] = rows[ADMIT] + pd.Timedelta(days=1)
            rows[BILLING] = billing_p95 * rng.uniform(4, 9, size=len(rows))
            if ADMISSION_TYPE in rows.columns:
                rows[ADMISSION_TYPE] = "Elective"

        else:  # pragma: no cover - guarded by ANOMALY_TYPES
            raise ValueError(f"unknown anomaly type {kind}")

        parts.append(rows)
        labels.extend([kind] * len(rows))

    injected = pd.concat(parts, ignore_index=True)
    combined = pd.concat([base, injected], ignore_index=True)

    is_anomaly = pd.Series(
        [False] * len(base) + [True] * len(injected), name="is_anomaly"
    )
    anomaly_type = pd.Series([""] * len(base) + labels, name="anomaly_type")

    return combined, is_anomaly, anomaly_type
