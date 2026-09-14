"""Payroll summary SQL built only from grounded allowlist columns."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.domain_sql.payroll_report_sql import (
    build_payroll_sql_from_grounding,
    try_build_payroll_detail_report_sql,
)
from app.services.ai_services.datamart.pipeline_common import validate_sql_with_grounding
from app.services.ai_services.datamart.domain_sql.report_spec import compile_report_spec
from app.services.ai_services.datamart.validation.report_spec_validate import validate_sql_against_report_spec
from app.services.ai_services.datamart.domain_sql.report_sql_router import try_build_sql_from_report_spec
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings

PAYROLL_Q = (
    "Prepare a payroll summary report by combining employee, payroll group, and "
    "employee snapshot details. Include employee name, employee ID, payroll group name, "
    "pay frequency, currency code, branch, and current basic salary."
)


def _payroll_view_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "employee_id",
                "emp_fullname",
                "branch",
                "payroll_group_name",
                "basic_salary",
                "period_label",
            ],
            "hr.dim_payroll_group": [
                "payroll_group_name",
                "payroll_frequency",
                "currency_code",
            ],
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "location_name",
                "payroll_group",
                "basic_salary",
            ],
            "hr.fact_payroll": [
                "employee_id",
                "basic_salary",
                "period_label",
            ],
        },
        source="test",
    )


def test_prefers_vw_payroll_summary_with_group_join():
    sql = build_payroll_sql_from_grounding(PAYROLL_Q, _payroll_view_grounding())
    assert sql is not None
    assert "vw_payroll_summary" in sql
    assert "dim_payroll_group" in sql
    assert "payroll_frequency" in sql
    assert "currency_code" in sql


def test_binding_passes_for_payroll_grounding():
    g = _payroll_view_grounding()
    sql = try_build_payroll_detail_report_sql(PAYROLL_Q, grounding=g)
    assert sql is not None
    assert validate_sql_bindings(sql, g) is None


def test_report_spec_router_produces_payroll_sql():
    spec = compile_report_spec(PAYROLL_Q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.template_id == "payroll.summary_detail"
    routed = try_build_sql_from_report_spec(PAYROLL_Q, spec, grounding=_payroll_view_grounding())
    assert routed is not None
    sql, tag = routed
    assert "vw_payroll_summary" in sql
    assert tag == "payroll_summary_view_template"
    assert validate_sql_against_report_spec(PAYROLL_Q, sql, spec) is None


def test_mart_fallback_when_no_view():
    g = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "location_name",
                "payroll_group",
                "basic_salary",
            ],
            "hr.dim_payroll_group": [
                "payroll_group_name",
                "payroll_frequency",
                "currency_code",
            ],
        },
        source="test",
    )
    sql = try_build_payroll_detail_report_sql(PAYROLL_Q, grounding=g)
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "dim_payroll_group" in sql
