import pandas as pd

from src.models.features import MODEL_FEATURES, build_features


def _frame():
    return pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "age": [30, 60, 45],
            "gender": ["Male", "Female", "Male"],
            "blood_type": ["A+", "O-", "B+"],
            "medical_condition": ["Cancer", "Asthma", "Cancer"],
            "date_of_admission": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "discharge_date": ["2024-01-11", "2024-01-25", "2024-03-02"],
            "doctor": ["D1", "D2", "D3"],
            "hospital": ["H1", "H2", "H3"],
            "insurance_provider": ["Aetna", "Cigna", "Aetna"],
            "billing_amount": [10_000.0, 20_000.0, 30_000.0],
            "room_number": [101, 102, 103],
            "admission_type": ["Urgent", "Elective", "Emergency"],
            "medication": ["m1", "m2", "m3"],
            "test_results": ["Normal", "Abnormal", "Normal"],
        }
    )


def test_los_is_computed_in_days():
    _, fe = build_features(_frame())
    assert fe["los_days"].tolist() == [10, -7, 1]


def test_negative_los_is_preserved_not_clipped():
    # A discharge before admission must survive into the features -- it is
    # exactly the record the pipeline exists to surface.
    _, fe = build_features(_frame())
    assert (fe["los_days"] < 0).any()


def test_billing_per_day_is_null_for_non_positive_stays():
    _, fe = build_features(_frame())
    assert pd.isna(fe.loc[1, "billing_per_day"])
    assert fe.loc[0, "billing_per_day"] == 1000.0


def test_model_matrix_contains_no_direct_identifiers():
    X, _ = build_features(_frame())
    for banned in ("name", "doctor", "hospital", "room_number"):
        assert not any(banned in c for c in X.columns)


def test_model_features_are_all_present():
    X, _ = build_features(_frame())
    assert set(MODEL_FEATURES).issubset(X.columns)
