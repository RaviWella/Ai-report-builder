"""Recruitment pipeline SQL template."""
from app.services.ai_services.datamart.domain_sql.recruitment_pipeline_sql import (
    try_build_recruitment_pipeline_sql,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_fast_path import try_resolve_deterministic_sql


def _recruitment_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr_semantic.fact_recruitment_pipeline": [
                "candidate_id",
                "recruitment_source",
                "appointment_date",
                "expected_joining_date",
                "branch_id",
            ],
            "hr_semantic.dim_candidate": [
                "candidate_id",
                "candidate_name",
                "email",
            ],
            "hr_semantic.dim_org_unit": [
                "org_unit_id",
                "org_unit_name",
            ],
        },
        source="test",
    )


def test_recruitment_pipeline_template():
    q = (
        "Prepare a recruitment pipeline report showing candidates sourced through "
        "LinkedIn and employee referrals, including candidate name, contact email, "
        "recruitment source, appointment date, expected joining date, and assigned branch. "
        "Include only candidates who are expected to join within the next 60 days"
    )
    sql = try_build_recruitment_pipeline_sql(q, grounding=_recruitment_grounding())
    assert sql is not None
    assert "fact_recruitment_pipeline" in sql
    assert "dim_candidate" in sql
    assert "linkedin" in sql.lower() or "referral" in sql.lower()
    assert "60 days" in sql
    assert "NULL::text" not in sql


def test_fast_path_recruitment_first():
    q = (
        "Prepare a recruitment pipeline report showing candidates sourced through "
        "LinkedIn and employee referrals"
    )
    resolved = try_resolve_deterministic_sql(q, grounding=_recruitment_grounding())
    assert resolved is not None
    assert resolved[1] == "recruitment_pipeline_template"
