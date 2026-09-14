"""Verified metric SQL templates from semantic catalog."""
from unittest.mock import MagicMock

from app.services.ai_services.datamart.domain_sql.metric_templates import (
    can_use_verified_metric_sql,
    question_wants_row_detail,
    sql_mismatches_detail_question,
    try_resolve_verified_metric_sql,
)
from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.semantic.semantic_layer import clear_catalog_cache
from app.services.ai_services.datamart.validation.validation_models import (
    RetrievalValidation,
    ValidationStatus,
)
_ctx_token = None


def setup_function() -> None:
    global _ctx_token
    clear_catalog_cache()
    _ctx_token = None


def teardown_function() -> None:
    global _ctx_token
    clear_catalog_cache()
    if _ctx_token is not None:
        reset_datamart_context(_ctx_token)
        _ctx_token = None


def _demo_tenant_ctx() -> None:
    global _ctx_token
    _ctx_token = set_datamart_context(
        DatamartRuntimeContext(
            tenant_id="demo_tenant",
            profile=DatamartProfile.TENANT_ETL,
            engine=MagicMock(),
            query_schemas=("hr_semantic", "hr", "hr_snap"),
            primary_schema="hr_semantic",
            database_name="hrm_wh_demo_tenant",
        )
    )


def test_workforce_report_does_not_use_verified_count():
    _demo_tenant_ctx()
    q = (
        "Generate a workforce report by combining employee and organization data. "
        "Include employee name, employee ID, company, branch, department"
    )
    assert question_wants_row_detail(q)
    insufficient = RetrievalValidation(
        status=ValidationStatus.INSUFFICIENT,
        missing_tables=["vw_payroll_summary"],
        message="Missing tables",
    )
    assert not can_use_verified_metric_sql(q, insufficient)
    assert try_resolve_verified_metric_sql(q, retrieval=insufficient) is None
    assert try_resolve_verified_metric_sql(q) is None


def test_top_paid_resolves_with_limit():
    _demo_tenant_ctx()
    q = "Show top 10 employees by basic salary from payroll"
    sufficient = RetrievalValidation(status=ValidationStatus.SUFFICIENT)
    out = try_resolve_verified_metric_sql(q, retrieval=sufficient)
    assert out is not None
    sql, metric, _narr = out
    assert metric == "top_paid"
    assert "LIMIT 10" in sql.upper()


def test_headcount_count_query():
    _demo_tenant_ctx()
    q = "What is the headcount?"
    sufficient = RetrievalValidation(status=ValidationStatus.SUFFICIENT)
    out = try_resolve_verified_metric_sql(q, retrieval=sufficient)
    assert out is not None
    sql, metric, _ = out
    assert metric in ("headcount", "employee_count")
    assert "COUNT" in sql.upper()


def test_scalar_mismatch_detected():
    q = "Generate a workforce report with employee name and branch"
    sql = "SELECT COUNT(DISTINCT employee_id) AS employee_count FROM hr.dim_employee"
    assert sql_mismatches_detail_question(q, sql)
