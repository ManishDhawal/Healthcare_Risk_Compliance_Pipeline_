{{ config(severity = 'warn') }}

-- 534 rows are exact duplicates across every column. In a real feed this
-- would usually mean a replayed batch rather than two identical episodes.

select
    name, date_of_admission, discharge_date, billing_amount, room_number,
    count(*) as n
from {{ ref('stg_healthcare') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
