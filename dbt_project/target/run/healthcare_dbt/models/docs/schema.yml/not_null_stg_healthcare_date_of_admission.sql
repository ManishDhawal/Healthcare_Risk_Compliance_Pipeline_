
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select date_of_admission
from "healthcare"."public"."stg_healthcare"
where date_of_admission is null



  
  
      
    ) dbt_internal_test