{% snapshot snap_designation %}

{{
    config(
        target_schema=var('snap_schema', target.name ~ '_hr_snap'),
        unique_key='designation_nk',
        strategy='timestamp',
        updated_at='_source_updated_at',
        invalidate_hard_deletes=True,
    )
}}

SELECT * FROM {{ ref('int_designation') }}

{% endsnapshot %}
