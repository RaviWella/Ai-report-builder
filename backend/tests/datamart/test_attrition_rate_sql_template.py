"""Attrition-rate report SQL template and binding rewrite."""
from app.services.ai_services.datamart.domain_sql.catalog_report_sql import (
    looks_like_attrition_rate_report,
    try_build_attrition_rate_report_sql,
)
from app.services.ai_services.datamart.sql.sql_binding_rewrite import try_binding_catalog_rewrite

ATTRITION_Q = "Which departments have the highest attrition rate?"


def test_attrition_rate_question_detected():
    assert looks_like_attrition_rate_report(ATTRITION_Q)


def test_attrition_rate_template_uses_semantic_views():
    sql = try_build_attrition_rate_report_sql(ATTRITION_Q)
    assert sql is not None
    assert "vw_turnover" in sql
    assert "vw_headcount" in sql
    assert "attrition_rate_pct" in sql
    assert " AS attrition_rate," not in sql
    assert " AS attrition_rate\n" not in sql
    assert "designation_department" in sql


def test_binding_rewrite_for_hallucinated_column():
    err = (
        "Column 'attrition_rate' is not in the grounded allowlist "
        "(unqualified column)."
    )
    sql = try_binding_catalog_rewrite(ATTRITION_Q, err, sql="SELECT attrition_rate FROM t")
    assert sql is not None
    assert "vw_turnover" in sql
