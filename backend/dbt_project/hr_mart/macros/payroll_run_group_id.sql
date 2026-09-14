{# Decode synthetic payroll_run_id: group*1e8 + year*1e4 + month*100 + half #}
{% macro payroll_run_group_id(run_id_column) %}
    ({{ run_id_column }} / 100000000)::integer
{% endmacro %}

{% macro payroll_period_label(year_column, month_column) %}
    to_char(
        make_date({{ year_column }}::integer, {{ month_column }}::integer, 1),
        'YYYY-MM'
    )
{% endmacro %}
