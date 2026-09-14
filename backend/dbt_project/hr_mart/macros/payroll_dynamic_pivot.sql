{# Dynamic wide paysheet columns — discovered from int_payroll_paysheet_vertical. #}

{% macro payroll_pivot_catalog_query(tenant_id=none) %}
    {% set tenant = tenant_id or var('tenant_id', target.name) %}
    select
        pivot_key,
        max(pivot_label) as pivot_label,
        min(display_order) as display_order
    from (
        select
            v.pivot_key,
            v.pivot_label,
            1000 + row_number() over (order by v.pivot_key) as display_order
        from {{ ref('int_payroll_paysheet_vertical') }} v
        where v.tenant_id = '{{ tenant }}'
          and v.pivot_key is not null
        group by v.pivot_key, v.pivot_label
    ) discovered
    group by pivot_key
    order by display_order, pivot_key
{% endmacro %}


{% macro payroll_pivot_sum_columns(tenant_id=none) %}
    {% if execute %}
        {% set cfg = run_query(payroll_pivot_catalog_query(tenant_id)) %}
        {% if cfg.rows | length == 0 %}
            sum(case when 1 = 0 then 0 else 0 end) as paysheet_no_dynamic_items
        {% else %}
            {% for row in cfg.rows %}
                sum(case
                    when pivot_key = '{{ row.pivot_key | replace("'", "''") }}'
                    then amount else 0
                end) as {{ row.pivot_key }}{{ "," if not loop.last }}
            {% endfor %}
        {% endif %}
    {% else %}
        sum(case when 1 = 0 then 0 else 0 end) as paysheet_no_dynamic_items
    {% endif %}
{% endmacro %}


{% macro payroll_pivot_coalesce_columns(alias='p', tenant_id=none) %}
    {% if execute %}
        {% set cfg = run_query(payroll_pivot_catalog_query(tenant_id)) %}
        {% if cfg.rows | length == 0 %}
            cast(null as numeric) as paysheet_no_dynamic_items
        {% else %}
            {% for row in cfg.rows %}
                coalesce({{ alias }}.{{ row.pivot_key }}, 0) as {{ row.pivot_key }}{{ "," if not loop.last }}
            {% endfor %}
        {% endif %}
    {% else %}
        cast(null as numeric) as paysheet_no_dynamic_items
    {% endif %}
{% endmacro %}
