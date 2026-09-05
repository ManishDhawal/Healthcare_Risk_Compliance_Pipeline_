{{ config(severity = 'warn') }}

-- 108 rows (0.19%) carry a negative billing amount, down to -$2,008.
--
-- Severity is 'warn' deliberately. Negative charges are legitimate in real
-- revenue data -- refunds, adjustments, reversals -- so failing the build
-- would be wrong. Warning keeps the count visible on every run so a change
-- in its size gets noticed.

select
    billing_amount
from {{ ref('stg_healthcare') }}
where billing_amount < 0
