import os, sys, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from src.models.features import load_staging, build_features
from src.config.settings import BASE_DIR



OUT_DIR = os.path.join(BASE_DIR, "data", "processed")
PRED_PATH = os.path.join(OUT_DIR, "predictions.csv")
METRICS_PATH = os.path.join(OUT_DIR, "model_metrics.json")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = load_staging()
    X, fe = build_features(df)


    # Pipeline: impute -> scale -> IsolationForest

    pipe = Pipeline(steps=[
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler(with_mean=False)),
        ("iso", IsolationForest(
            n_estimators=300,
            contamination="auto",
            random_state=42
        ))
    ])

    pipe.fit(X)
    scores = pipe.named_steps["iso"].score_samples(pipe.named_steps["scale"].transform(
        pipe.named_steps["impute"].transform(X)
    ))

    # Lower score = more anomalousl; convert to a risk score 0..1 (higher = riskier)
    # Rank-based normalization (monotonic, uses only observed data)
    ranks = pd.Series(scores).rank(method="average", pct=True) # 0..1 where 1 = highest (least risky)
    risk = 1 - ranks                                           # 1 = most risky


    # Output table for BI (no PII, but include name if you want privately)
    out = fe.copy()
    out["risk_score"] = risk.values
    out["anomaly_score_raw"] = scores

    # Optional: drop PII for shareable exports (keep for now; you cam remove "name"/"doctor" later)

    out.to_csv(PRED_PATH, index=False)


    # Simple metrics to log distribution
    metrics = {
        "rows": int(len(out)),
        "risk_min": float(out["risk_score"].min()),
        "risk_max": float(out["risk_score"].max()),
        "risk_mean": float(out["risk_score"].mean()),
        "risk_p95": float(out["risk_score"].quantile(0.95)),
        "nulls_billing": int(out["billing_amount"].isna().sum()),
        "nulls_los_days": int(out["discharge_date"].isna().sum() + out["date_of_admission"].isna().sum())
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved predictions -> {PRED_PATH}")
    print(f"Saved model metrics -> {METRICS_PATH}")

if __name__ == "__main__":
    main()
