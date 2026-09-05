# Healthcare Risk & Compliance Pipeline

An end-to-end analytics pipeline over hospital admissions: CSV → validated
parquet → Postgres → dbt staging and marts → an anomaly detector that ranks
records for compliance review, **evaluated against ground truth it manufactures
itself.**

The interesting part is not the pipeline. It is that the detector is measured
at all, and what the measurement turned up.

---

## The data is synthetic

The source is the Kaggle [Healthcare Dataset](https://www.kaggle.com/datasets/prasad22/healthcare-dataset),
published by its author as *"dummy data."* Every name, provider and charge is
generated — there are 39,876 distinct hospital values across 55,500 rows, which
is not how real hospital data looks.

This is stated first because it constrains what the project can claim. **No
number produced here is a finding about healthcare.** The artefact under review
is the pipeline: how the data is validated, where corrections live, how the
model is evaluated, and what leaves the machine. Real patient data could not be
published, and a project built on it could not be shown to anyone.

---

## Quickstart

Runs end to end with no database:

```bash
pip install -r requirements.txt
# place the Kaggle CSV at data/raw/healthcare_dataset.csv
make all          # ingest -> score -> test
```

No `make` (most Windows installs), or you would rather see the steps:

```bash
python -m src.ingest.ingest_validate    # CSV -> validated parquet
python -m src.models.train              # inject, fit, evaluate, export
pytest -q
```

Every module runs with `python -m`, not as a file path. `python src/models/train.py`
puts `src/models/` on the import path instead of the repo root and fails on
`import src.config`.

With Postgres, for the full warehouse path:

```bash
cp .env.example .env      # set PG_* variables
make ingest warehouse dbt score
```

`load_frame()` prefers the warehouse and falls back to the parquet, so the
pipeline is runnable by anyone who clones it. That matters more than it sounds:
a project nobody can execute is a project nobody can evaluate.

---

## Architecture

```
data/raw/healthcare_dataset.csv
        │
        │  src/ingest/          contract check: shape and columns only
        ▼
data/processed/clean.parquet
        │
        │  src/warehouse/       load to Postgres  (optional)
        ▼
public.stg_healthcare_raw
        │
        │  dbt                  typing, date parsing, snake_case
        ▼
staging.stg_healthcare ──────────► marts.mart_kpis   (monthly KPIs for BI)
        │
        │  src/quality/         inject labelled anomalies at a known rate
        │  src/models/          IsolationForest → ranked risk score
        │  src/models/evaluate  precision@k, recall@k, AP against the labels
        ▼
data/processed/risk_scores.csv    de-identified, ranked
data/processed/model_metrics.json
```

Value-level corrections live in dbt, never in the loader. A loader that quietly
repairs data is a loader nobody can audit; a dbt test that warns on 108 negative
charges is visible in every run.

---

## Making an unsupervised model measurable

An anomaly detector on unlabelled data produces an ordering that nobody can
check. The first version of this project scored records with
`1 - rank(pct=True)` over IsolationForest output and reported the result. That
statistic is uniform on `[0, 1]` **by construction** — its mean was 0.49999 and
its 95th percentile 0.94998, which is what a uniform distribution looks like and
not evidence of anything. There was no way to tell whether a high score meant a
record deserved review.

The fix is to manufacture ground truth. `src/quality/inject.py` appends copies of
real admissions mutated into five failure modes a revenue-integrity review would
actually flag, at a 1% contamination rate:

| Failure mode | What it represents |
|---|---|
| `negative_los` | Discharge recorded before admission |
| `extreme_los` | Stay beyond 400 days — usually an unclosed episode |
| `billing_high_outlier` | Charge 12–30× the median for the same condition |
| `billing_negative` | Large negative charge, well outside the natural range |
| `short_stay_high_bill` | One-day elective stay billed like a major episode |

The detector never sees the labels. It fits on the contaminated data, ranks
everything, and the ranking is scored against the labels afterwards.

**This measures whether the detector surfaces the failure modes I thought of.**
It says nothing about failure modes I did not. That is a real limit, and it is
the reason the per-mode breakdown below matters more than the headline number.

---

## Results

Reproduce with `make score` (seed 42, 555 injected anomalies in 56,055 rows).

| Metric | Value |
|---|---|
| Average precision | **0.887** |
| Precision @ 100 | 1.000 — 101× base rate |
| Precision @ 500 | 0.842 — 85× base rate |
| Recall @ 1000 | 0.919 |

Per failure mode, recall in the top 1,000:

| Failure mode | Caught | Recall |
|---|---|---|
| `billing_high_outlier` | 111 / 111 | 1.000 |
| `extreme_los` | 111 / 111 | 1.000 |
| `short_stay_high_bill` | 111 / 111 | 1.000 |
| `billing_negative` | 110 / 111 | 0.991 |
| `negative_los` | 67 / 111 | **0.604** |

### Two defaults were doing most of the damage

The benchmark's first job was to score the pipeline as it already stood. It came
back at **average precision 0.319**, with two failure modes at zero recall. Two
changes took it to 0.887:

**Dropping the one-hot encoded categoricals from the model input.**
IsolationForest chooses its split feature uniformly at random. Eleven
near-uniform indicator columns alongside four informative ones meant most splits
carried no signal. The categoricals are still built — the BI layer groups by
them — they are just not model inputs.

**Raising `max_samples` from the sklearn default of 256 to 8192.** Each tree
draws its split thresholds from a subsample; at a 1% contamination rate a
256-row subsample almost never contains an anomaly, so moderate outliers sit
inside the sampled range and take as long to isolate as ordinary records.
`extreme_los` recall went from 0.07 to 1.00 on this change alone.

Neither was a modelling insight. Both were defaults nobody had reason to
question until there was a number that moved.

### The failure mode the model cannot fix

`negative_los` stays at 0.604 under every configuration tried, while everything
else reaches 0.99+. The reason is not tuning.

A discharge before an admission is **invalid, not unusual.** A stay of −12 days
sits comfortably inside the numeric spread of ordinary stays, so a detector that
measures distance-from-typical scores it as unremarkable. No amount of tuning an
outlier model changes that, because the model is answering the wrong question.

So it moved to where it belongs:
`dbt_project/tests/assert_discharge_after_admission.sql`. Rules enforce validity;
the model handles what is merely strange. Splitting the two is the actual
architectural conclusion of this project.

---

## What the tests found in the source data

`dbt build` runs 11 tests. Three surface genuine issues in the source:

- **108 rows (0.19%) carry negative billing**, down to −$2,008. Flagged at
  `warn`, not `error`: refunds and adjustments are legitimate in real revenue
  data, so failing the build would be wrong. Warning keeps the count visible so a
  change in its size gets noticed.
- **534 rows are exact duplicates** across every column — in a real feed, a
  replayed batch rather than two identical episodes.
- **0 rows violate the discharge-after-admission constraint.** The test passes
  today and exists so that it will fail loudly the day it stops passing.

---

## Privacy

`risk_scores.csv` carries no direct identifiers. `name`, `doctor`, `hospital`
and `room_number` are dropped at export, not marked optional — the export is the
artefact most likely to be shared, and a compliance project that leaks
identifiers in its own output has argued against itself. Raw and processed data
are gitignored; only code and documentation are tracked.

---

## Dashboard

`dashboards/powerbi/Healthcare_risk.pbix`, previewed in `images/`.

| Measure | Value |
|---|---|
| Admissions | 55,500 |
| Total billing | $1.417 B |
| Average billing per admission | $25,539 |
| Average length of stay | 15.51 days |

Pages cover admissions trend by month, billing by insurance provider, billing
against length of stay, risk-tier segmentation, and average billing by
admission type. Definitions for every measure are in
[`docs/METRICS.md`](docs/METRICS.md) — including the ones that are easy to get
wrong, like billing being attributed to the admission month rather than the
discharge month.

### What the dashboard actually showed

The useful finding was a negative one, and it is the reason the synthetic-data
warning sits at the top of this README rather than in a footnote.

**Nothing in this data varies with anything else.**

- Length of stay against billing: Pearson **r = −0.006**. There is no
  relationship. An earlier version of this README claimed a "strong correlation
  between LOS and billing, indicating cost drivers"; that claim was wrong and
  has been removed.
- Mean billing by insurance provider spans **$25,389 to $25,616** — a 0.9%
  spread across five providers with roughly 11,000 admissions each.
- Mean billing by admission type spans **$25,497 to $25,602**. Elective,
  urgent and emergency admissions cost the same.
- Abnormal test results run **32.9%–33.9%** across every provider.

Real hospital billing does not behave like this. Emergency admissions cost more
than elective ones; longer stays cost more than shorter ones; payer mix moves
the average. Flatness this uniform across every cut is the signature of
independently sampled columns, which is exactly what the source is.

So the dashboard's honest output is not "high-risk patients concentrate in
Medicare." It is: **these columns were generated independently, so no
cross-sectional insight drawn from them is real.** The visuals are built to
demonstrate the modelling and metric-definition work, not to support conclusions
about healthcare.

The anomaly detection in this pipeline still works, because it looks for
records that are internally inconsistent — a negative stay, a charge that does
not match its episode — rather than for relationships between columns that were
never there.

## Layout

```
src/
  config/      paths and env loading
  ingest/      CSV contract check -> parquet
  warehouse/   parquet -> Postgres
  quality/     labelled anomaly injection
  models/      features, detector, ranking metrics
  utils/       io helpers
dbt_project/
  models/staging/   typed view over the raw table
  models/marts/     monthly KPIs
  models/docs/      column docs, not_null and accepted_values tests
  tests/            singular tests for validity constraints
tests/unit/    26 tests covering injection, metrics, features, contract
dashboards/
  powerbi/     Healthcare_risk.pbix
images/        dashboard screenshots used above
docs/
  METRICS.md   metric definitions and lineage, source column to KPI
```

---

## What this does not do

- It does not prove the detector finds anomalies outside the five injected
  modes. Nothing here could.
- It has no orchestration. An Airflow DAG would be five tasks wrapping the
  Makefile targets, and an empty `airflow_dags/` directory would be worse than
  none.
- The marts layer is small — one KPI table. It exists to feed the BI layer, not
  to demonstrate dbt breadth.
