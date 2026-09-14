-- Union loan + installment processed deductions (§7.4 sources).

{{ config(materialized='view') }}

select * from {{ ref('stg_processed_loan_data') }}
union all
select * from {{ ref('stg_processed_installment_payment_data') }}
