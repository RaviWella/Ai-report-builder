-- dim_date — calendar dimension (day grain; join month-start dates for snapshot_month_sk).

{{ config(materialized='table') }}

WITH date_spine AS (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('1990-01-01' as date)",
        end_date="cast('2035-12-31' as date)"
    ) }}
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['date_day']) }}     AS date_sk,
        date_day                                               AS calendar_date,
        EXTRACT(YEAR FROM date_day)::int                        AS year,
        EXTRACT(MONTH FROM date_day)::int                       AS month_number,
        EXTRACT(DAY FROM date_day)::int                         AS day_of_month,
        EXTRACT(DOW FROM date_day)::int                         AS day_of_week,
        TO_CHAR(date_day, 'YYYY-MM')                            AS year_month,
        DATE_TRUNC('month', date_day)::date                     AS month_start_date,
        (DATE_TRUNC('month', date_day) + INTERVAL '1 month - 1 day')::date
                                                                AS month_end_date,
        EXTRACT(QUARTER FROM date_day)::int                     AS quarter,
        CASE WHEN EXTRACT(DOW FROM date_day) IN (0, 6) THEN TRUE ELSE FALSE END
                                                                AS is_weekend
    FROM date_spine
)

SELECT * FROM final
