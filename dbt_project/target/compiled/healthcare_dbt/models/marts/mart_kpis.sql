

with base as (
  select
    *,
    (discharge_date - date_of_admission) as los_days  -- integer days
  from "healthcare"."public"."stg_healthcare"
),
monthly as (
  select
    date_trunc('month', date_of_admission) as month,
    count(*)                                as admissions,
    avg(los_days::numeric)                  as avg_los_days,   -- <— avg over integer days
    sum(billing_amount)                     as total_billing,
    avg(billing_amount)                     as avg_billing
  from base
  where los_days is not null                -- avoid nulls in avg
  group by 1
)
select * from monthly