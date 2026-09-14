-- RAW layer view — CDC-compatible envelope over ETL loads (§5.1).
-- When Debezium lands in audit schema, point sources here instead of stg_*.

{{ config(materialized='view') }}

select
    d.*,
    'c'::varchar(1)                                         as __op,
    coalesce(d.updated_at, d.created_at, now())             as _cdc_timestamp,
    coalesce(d.updated_at, d.created_at, now())             as _source_updated_at
from {{ source('payroll_processed', 'processed_sal_basic_data') }} d
