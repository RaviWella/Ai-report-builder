"""ReportSpec compile: domain, tables, template routing."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.domain_sql.report_spec import (
    ReportDomain,
    ReportType,
    compile_report_spec,
)
from app.services.ai_services.datamart.domain_sql.report_sql_router import try_build_sql_from_report_spec

LEAVE_Q = (
    "Generate a report of employees and their leave details by combining employee "
    "and leave transaction information. Include employee name, employee ID, branch, "
    "leave type, leave start date, leave end date, total leave days, and leave status. "
    "Display only approved leave requests"
)

ATTRITION_Q = "Which department has the highest attrition rate?"

RECRUITMENT_Q = (
    "Prepare a recruitment pipeline report showing candidates sourced through LinkedIn "
    "and employee referrals, including candidate name and expected joining date."
)


def test_recruitment_not_classified_as_workforce():
    spec = compile_report_spec(RECRUITMENT_Q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.domain != ReportDomain.WORKFORCE
    assert "mart_employee_current" not in spec.required_tables


def test_compile_leave_domain_and_template():
    spec = compile_report_spec(LEAVE_Q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.domain == ReportDomain.LEAVE
    assert spec.report_type == ReportType.DETAIL_LIST
    assert spec.template_id == "leave.detail_list"
    assert "fact_leave_transaction" in spec.required_tables
    assert "approved_leave" in spec.sql_filters


def test_compile_attrition_domain():
    spec = compile_report_spec(ATTRITION_Q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.domain == ReportDomain.ATTRITION
    assert spec.template_id == "attrition.rate_by_department"


def test_refine_intent_yields_generic_spec():
    spec = compile_report_spec("add branch column", chat_intent=ChatIntent.REFINE_SQL)
    assert spec.domain == ReportDomain.GENERIC
    assert not spec.required_tables or spec.required_tables == ["dim_employee"]


def test_router_builds_leave_sql_from_spec():
    from app.services.ai_services.datamart.schema_broker import SchemaGrounding

    spec = compile_report_spec(LEAVE_Q, chat_intent=ChatIntent.NEW_QUERY)
    g = SchemaGrounding(
        columns_by_table={
            "hr.fact_leave_transaction": [
                "employee_id",
                "leave_type_id",
                "leave_start_date",
                "leave_end_date",
                "leave_days",
                "leave_status_name",
            ],
            "hr.dim_leave_type": ["leave_type_id", "leave_type_name"],
            "hr.dim_employee": [
                "employee_id",
                "employee_no",
                "full_name",
                "branch_name",
                "is_current",
            ],
        },
        source="test",
    )
    routed = try_build_sql_from_report_spec(LEAVE_Q, spec, grounding=g)
    assert routed is not None
    sql, source = routed
    assert source == "leave_detail_template"
    assert "fact_leave_transaction" in sql
