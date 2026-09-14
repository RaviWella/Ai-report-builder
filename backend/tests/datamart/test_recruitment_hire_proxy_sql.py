"""Recruitment hire-lifecycle proxy when pipeline facts are absent."""
from app.services.ai_services.datamart.domain_sql.recruitment_hire_proxy_sql import (
    try_build_recruitment_hire_proxy_sql,
    warehouse_has_recruitment_pipeline,
)
from app.services.ai_services.datamart.domain_sql.recruitment_pipeline_sql import (
    try_build_recruitment_pipeline_sql,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def _lifecycle_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr.fct_lifecycle_event": [
                "employee_sk",
                "event_category",
                "event_name",
                "approved_date",
                "effective_date",
            ],
            "hr.mart_employee_current": [
                "employee_sk",
                "emp_fullname",
                "join_date",
                "location_name",
                "employee_category",
                "employment_type",
                "designation",
            ],
            "hr.dim_employee": ["employee_sk", "email", "is_current"],
        },
        source="test",
    )


def test_hire_proxy_when_no_pipeline_fact():
    q = (
        "Which recruitment sources produced the most candidates appointed "
        "in the last quarter?"
    )
    sql = try_build_recruitment_hire_proxy_sql(q, grounding=_lifecycle_grounding())
    assert sql is not None
    assert "fct_lifecycle_event" in sql
    assert "fact_recruitment_pipeline" not in sql


def test_pipeline_template_falls_back_to_proxy():
    q = (
        "Prepare a recruitment pipeline report showing candidates sourced through "
        "LinkedIn and employee referrals"
    )
    g = _lifecycle_grounding()
    assert not warehouse_has_recruitment_pipeline(g)
    sql = try_build_recruitment_pipeline_sql(q, grounding=g)
    assert sql is not None
    assert "hire_pipeline" in sql.lower()
