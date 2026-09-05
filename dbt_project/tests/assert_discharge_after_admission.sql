-- A discharge recorded before the admission is invalid, not unusual.
--
-- This is the constraint the anomaly detector cannot reliably enforce: a
-- negative length of stay sits well inside the numeric range of ordinary
-- stays, so an outlier model scores it as unremarkable. On the labelled
-- benchmark the detector recovers only 60% of injected negative-stay rows
-- while catching 99-100% of every other failure mode. Validity belongs in a
-- test; the model handles what is merely strange.

select
    date_of_admission,
    discharge_date,
    (discharge_date - date_of_admission) as los_days
from {{ ref('stg_healthcare') }}
where discharge_date < date_of_admission
