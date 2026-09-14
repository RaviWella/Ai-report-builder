"""Pre-execute ReportSpec validation."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.validation.retrieval_validator import validate_retrieval
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.semantic.semantic_layer import resolve_semantics
from app.services.ai_services.datamart.domain_sql.report_spec import (
    ReportDomain,
    compile_report_spec,
)
from app.services.ai_services.datamart.validation.report_spec_validate import (
    _tables_in_sql,
    validate_retrieval_for_spec,
    validate_sql_against_report_spec,
)

LEAVE_Q = (
    "Generate a report of employees and their leave details. "
    "Display only approved leave requests"
)

MART_BALANCE_SQL = """
SELECT m.emp_fullname AS employee_name,
       m.emp_no AS employee_id,
       flb.leave_type_name AS leave_type,
       flb.period_label AS leave_start_date,
       flb.days_approved AS total_leave_days,
       'approved' AS leave_status
FROM hr.mart_employee_current m
JOIN hr.fact_leave_balance flb ON m.employee_id::text = flb.source_emp_id::text
WHERE flb.days_approved > 0
LIMIT 100
"""


def test_tables_in_sql_parses_schema_qualified_names():
    sql = "SELECT * FROM hr.fact_leave_transaction f JOIN hr.dim_leave_type t ON 1=1"
    assert "fact_leave_transaction" in _tables_in_sql(sql)
    assert "dim_leave_type" in _tables_in_sql(sql)


def test_mart_plus_balance_passes_leave_spec():
    spec = compile_report_spec(LEAVE_Q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.domain == ReportDomain.LEAVE
    err = validate_sql_against_report_spec(LEAVE_Q, MART_BALANCE_SQL, spec)
    assert err is None, err


def test_workforce_roster_ok_with_mart_only():
    q = "List employee name and reporting immediate supervisor"
    spec = compile_report_spec(q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.domain == ReportDomain.WORKFORCE
    assert "dim_employee" not in spec.required_tables
    err = validate_retrieval_for_spec(spec, ["mart_employee_current"])
    assert err is None, err


def test_attendance_employee_list_ok_with_mart_only():
    q = "Show the employees assigned to attendance approval groups"
    spec = compile_report_spec(q, chat_intent=ChatIntent.NEW_QUERY)
    assert spec.domain == ReportDomain.ATTENDANCE
    assert "dim_employee" not in spec.required_tables
    assert "approved_leave" not in spec.sql_filters
    err = validate_retrieval_for_spec(
        spec,
        [
            "mart_employee_current",
            "vw_attendance_summary",
            "fact_attendance",
            "dim_org_unit",
        ],
    )
    assert err is None, err


def test_attendance_retrieval_ok_with_vw_not_monthly_mart():
    q = "Show the employees assigned to attendance approval groups"
    grounded = [
        "dim_designation",
        "mart_employee_current",
        "vw_headcount",
        "vw_attendance_summary",
        "dim_employee",
        "dim_org_unit",
        "fact_attendance",
        "dim_shift",
    ]
    cols = {f"hr.{t}": ["col"] for t in grounded}
    sem = resolve_semantics(q)
    rv = validate_retrieval(
        question=q,
        grounding=SchemaGrounding(columns_by_table=cols),
        semantics=sem,
        schema_links=[],
        chat_intent=ChatIntent.NEW_QUERY,
    )
    assert "mart_attendance_monthly_summary" not in (rv.missing_tables or []), rv.message
    assert rv.status.value != "insufficient", rv.message
