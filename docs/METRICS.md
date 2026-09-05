# Metric dictionary and lineage

Every metric this pipeline publishes, what it means, how it is computed, and
which source column it descends from. Kept alongside the code so a definition
and its implementation change in the same commit.

The audience is whoever is asked "where does this number come from?" six months
from now.

---

## Column lineage

Source extract → staging → mart. Names in the source CSV are Title Case; dbt
renames to snake_case and casts. No values are altered in transit.

| Source column (CSV) | Staged column | Type | Transformation |
|---|---|---|---|
| `Name` | `name` | text | passthrough — dropped before any export |
| `Age` | `age` | numeric | cast |
| `Gender` | `gender` | text | passthrough, `accepted_values` tested |
| `Blood Type` | `blood_type` | text | passthrough |
| `Medical Condition` | `medical_condition` | text | passthrough |
| `Date of Admission` | `date_of_admission` | date | regex-guarded parse of `MM/DD/YYYY` or `YYYY-MM-DD`; null on neither |
| `Discharge Date` | `discharge_date` | date | same parse rules |
| `Doctor` | `doctor` | text | passthrough — dropped before any export |
| `Hospital` | `hospital` | text | passthrough — dropped before any export |
| `Insurance Provider` | `insurance_provider` | text | passthrough |
| `Billing Amount` | `billing_amount` | numeric | cast; negatives preserved and warned on |
| `Room Number` | `room_number` | integer | cast — dropped before any export |
| `Admission Type` | `admission_type` | text | passthrough, `accepted_values` tested |
| `Medication` | `medication` | text | passthrough |
| `Test Results` | `test_results` | text | passthrough, `accepted_values` tested |

The dual-format date parse exists because the source mixes both layouts. The
branch falls through to `null` rather than erroring, so a malformed date becomes
a visible `not_null` test failure instead of a silent build break.

---

## Derived metrics

### `los_days` — length of stay

**Definition.** Whole days between admission and discharge.
**Computed.** `discharge_date - date_of_admission`, in `mart_kpis` and in
`build_features()`.
**Lineage.** `Date of Admission`, `Discharge Date`.

**Negative values are preserved, not clipped.** A negative stay is a data
integrity failure and clipping it to zero would hide exactly the record the
pipeline exists to surface. It is caught by
`assert_discharge_after_admission.sql`, not by the model — see the README for
why.

A same-day admission and discharge yields `0`, not `1`. If the business
definition is "days billed," that is off by one and the definition should change
here first.

### `billing_per_day` — charge intensity

**Definition.** Billing amount divided by length of stay.
**Computed.** `billing_amount / los_days`, **null when `los_days <= 0`.**
**Lineage.** `Billing Amount`, `Date of Admission`, `Discharge Date`.

Separates a large charge earned over three weeks from the same charge run up
overnight. Null rather than infinite for non-positive stays; the imputer fills
those with the median at model time, which is recorded here because it means a
negative-stay record enters the model with an ordinary-looking intensity.

### `avg_los_days` — average length of stay, monthly

**Definition.** Mean `los_days` across admissions in a calendar month.
**Computed.** `mart_kpis`, grouped by `date_trunc('month', date_of_admission)`.
**Grain.** One row per admission month.

**Rows with a null `los_days` are excluded** from the average. The count in
`admissions` does not apply that filter, so `admissions` and the denominator
behind `avg_los_days` can differ. That is deliberate — a missing discharge date
should not remove an admission from the volume count — but it will be asked
about, so it is written down.

### `total_billing` / `avg_billing` — monthly charges

**Definition.** Sum and mean of `billing_amount` by admission month.
**Computed.** `mart_kpis`.
**Lineage.** `Billing Amount`.

Attributed to the **admission** month, not the discharge month. An episode
spanning a month boundary lands entirely in the month it started. The
alternative — attributing to discharge, or apportioning across days — is
defensible too; this pipeline picks one and says so.

Negative charges are included. Excluding them would inflate both figures and
break reconciliation against the source total.

### `risk_score` — anomaly ranking

**Definition.** Negated IsolationForest `score_samples`. Higher means further
from typical.
**Computed.** `src/models/train.py`.
**Inputs.** `age`, `billing_amount`, `los_days`, `billing_per_day`.
**Lineage.** `Age`, `Billing Amount`, `Date of Admission`, `Discharge Date`.

**This is a ranking, not a probability.** The scale has no units and no
calibration; a score of 0.65 does not mean 65% likely to be a problem. It exists
to order a review queue, and it is only meaningful relative to other scores in
the same run.

An earlier version rank-normalised this to `[0, 1]`, which produced a uniform
distribution carrying no information. Do not reintroduce that.

**Known limit.** Validated only against five injected failure modes. Recall is
0.99+ for four of them and 0.60 for `negative_los`. See the README.

---

## Evaluation metrics

| Metric | Definition | Why this one |
|---|---|---|
| `precision@k` | Share of the top *k* ranked records that are true anomalies | Matches how a queue is worked: an analyst gets through *k* items |
| `recall@k` | Share of all anomalies appearing in the top *k* | Says what the queue misses |
| `lift@k` | `precision@k` ÷ base rate | 1.0 means no better than random; makes the headline honest |
| `average_precision` | Area under the precision-recall curve over the full ranking | Single comparable number across configurations |

Precision-recall rather than ROC throughout, because at a 1% base rate ROC-AUC
looks flattering regardless of whether the ranking is useful.

---

## Changing a definition

1. Edit the definition here first.
2. Change the dbt model or feature code to match.
3. Update or add the test that pins it.
4. One commit, all three.

A metric whose definition lives only in a dashboard tooltip is a metric that
will quietly mean two different things within a year.
