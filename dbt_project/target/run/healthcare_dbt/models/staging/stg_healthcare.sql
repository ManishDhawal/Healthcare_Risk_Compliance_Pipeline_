
  create view "healthcare"."public"."stg_healthcare__dbt_tmp"
    
    
  as (
    

with raw as (
  select *
  from "healthcare"."public"."stg_healthcare_raw"
),
typed as (
  select
    "Name"                                   as name,
    ("Age")::numeric                         as age,
    "Gender"                                 as gender,
    "Blood Type"                             as blood_type,
    "Medical Condition"                      as medical_condition,
    -- admission date: handle MM/DD/YYYY and YYYY-MM-DD
    case
      when trim("Date of Admission") ~ '^\d{1,2}/\d{1,2}/\d{4}$'
        then to_date(trim("Date of Admission"), 'MM/DD/YYYY')
      when trim("Date of Admission") ~ '^\d{4}-\d{2}-\d{2}$'
        then to_date(trim("Date of Admission"), 'YYYY-MM-DD')
      else null
    end                                         as date_of_admission,

    "Doctor"                                  as doctor,
    "Hospital"                                as hospital,
    "Insurance Provider"                      as insurance_provider,
    ("Billing Amount")::numeric               as billing_amount,
    ("Room Number")::integer                  as room_number,
    "Admission Type"                          as admission_type,

    -- discharge date: same dual-format handling
    case
      when trim("Discharge Date") ~ '^\d{1,2}/\d{1,2}/\d{4}$'
        then to_date(trim("Discharge Date"), 'MM/DD/YYYY')
      when trim("Discharge Date") ~ '^\d{4}-\d{2}-\d{2}$'
        then to_date(trim("Discharge Date"), 'YYYY-MM-DD')
      else null
    end                                         as discharge_date,

    "Medication"                              as medication,
    "Test Results"                            as test_results
  from raw
)
select * from typed
  );