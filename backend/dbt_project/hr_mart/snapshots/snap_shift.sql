{% snapshot snap_shift %}

{{
    config(
        target_schema=var('snap_schema', target.name ~ '_hr_snap'),
        unique_key='shift_nk',
        strategy='timestamp',
        updated_at='_source_updated_at',
        invalidate_hard_deletes=True,
    )
}}

SELECT * FROM {{ ref('int_shift') }}

{% endsnapshot %}
