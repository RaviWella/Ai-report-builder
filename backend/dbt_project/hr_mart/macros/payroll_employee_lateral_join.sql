{# PIT join to dim_employee using process_timestamp (month-end fallback in int models). #}
{% macro payroll_employee_lateral_join(src_alias) %}
left join lateral (
    select d.employee_sk
    from {{ ref('dim_employee') }} d
    where trim(d.tenant_id::text) = trim({{ src_alias }}.tenant_id::text)
      and d.source_emp_id = {{ src_alias }}.source_emp_id
      and coalesce(nullif(trim(d.source_system::text), ''), '{{ var("source_system") }}')
          = coalesce(nullif(trim({{ src_alias }}.source_system::text), ''), '{{ var("source_system") }}')
    order by
        case
            when {{ src_alias }}.process_timestamp >= d.valid_from
             and {{ src_alias }}.process_timestamp < d.valid_to
            then 0
            else 1
        end,
        case when d.is_current then 0 else 1 end,
        d.valid_from desc
    limit 1
) emp on true
{% endmacro %}
