import numpy as np
import pandas as pd
import pytest

from src.quality.inject import ANOMALY_TYPES, inject


@pytest.fixture
def frame():
    n = 2000
    rng = np.random.default_rng(0)
    admit = pd.to_datetime("2023-01-01") + pd.to_timedelta(
        rng.integers(0, 365, n), unit="D"
    )
    return pd.DataFrame(
        {
            "date_of_admission": admit,
            "discharge_date": admit + pd.to_timedelta(rng.integers(1, 30, n), unit="D"),
            "billing_amount": rng.uniform(1_000, 50_000, n),
            "age": rng.integers(18, 90, n),
            "medical_condition": rng.choice(["Cancer", "Asthma", "Obesity"], n),
            "admission_type": rng.choice(["Urgent", "Emergency", "Elective"], n),
        }
    )


def test_every_failure_mode_is_represented(frame):
    _, _, kinds = inject(frame, rate=0.05, seed=1)
    present = {k for k in kinds.unique() if k}
    assert present == set(ANOMALY_TYPES)


def test_original_rows_are_untouched(frame):
    combined, is_anom, _ = inject(frame, rate=0.02, seed=1)
    original = combined.loc[~is_anom].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        original[frame.columns], frame.reset_index(drop=True), check_dtype=False
    )


def test_labels_align_with_rows(frame):
    combined, is_anom, kinds = inject(frame, rate=0.02, seed=1)
    assert len(combined) == len(is_anom) == len(kinds)
    assert int(is_anom.sum()) == int(round(len(frame) * 0.02))
    assert (kinds[~is_anom] == "").all()


def test_negative_los_rows_really_are_negative(frame):
    combined, _, kinds = inject(frame, rate=0.05, seed=1)
    rows = combined[kinds == "negative_los"]
    los = (rows["discharge_date"] - rows["date_of_admission"]).dt.days
    assert (los < 0).all()


def test_extreme_los_rows_exceed_a_year(frame):
    combined, _, kinds = inject(frame, rate=0.05, seed=1)
    rows = combined[kinds == "extreme_los"]
    los = (rows["discharge_date"] - rows["date_of_admission"]).dt.days
    assert (los > 365).all()


def test_reproducible_for_a_fixed_seed(frame):
    a, _, _ = inject(frame, rate=0.02, seed=7)
    b, _, _ = inject(frame, rate=0.02, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_rate_must_leave_room_for_every_mode(frame):
    with pytest.raises(ValueError, match="every failure mode"):
        inject(frame, rate=0.001, seed=1)


@pytest.mark.parametrize("bad", [0, 1, -0.1, 1.5])
def test_rate_bounds(frame, bad):
    with pytest.raises(ValueError):
        inject(frame, rate=bad, seed=1)
