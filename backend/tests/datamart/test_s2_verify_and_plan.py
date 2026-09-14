"""S2: query plan parsing, link-table guard, verify_sql entry."""
from __future__ import annotations

from app.services.ai_services.datamart.pipeline.query_plan import parse_query_plan
from app.services.ai_services.datamart.pipeline.sql_table_guard import assert_sql_tables_in_link
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def test_parse_query_plan_filters_unknown_tables():
    raw = """{
      "tables": ["fact_recruitment_pipeline", "dim_candidate", "fake_table"],
      "joins": ["rp.candidate_id = c.candidate_id"],
      "filters": ["linkedin or referral"],
      "select_columns": ["candidate_name", "contact_email"],
      "aggregations": null,
      "order_limit": "ORDER BY 1 LIMIT 100"
    }"""
    plan = parse_query_plan(
        raw,
        allowed_tables=[
            "fact_recruitment_pipeline",
            "dim_candidate",
            "dim_org_unit",
        ],
    )
    assert plan is not None
    assert "fact_recruitment_pipeline" in plan.tables
    assert "fake_table" not in plan.tables


def test_link_guard_rejects_leave_table_on_recruitment_link():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.fact_recruitment_pipeline": ["candidate_id"],
            "hr.dim_candidate": ["candidate_name"],
        },
        source="test",
    )
    sql = "SELECT * FROM hr.fact_leave_balance lb JOIN hr.dim_candidate c ON TRUE"
    err = assert_sql_tables_in_link(sql, grounding)
    assert err is not None
    assert "fact_leave_balance" in err
