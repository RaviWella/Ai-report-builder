"""Leave SQL built only from grounded allowlist columns."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.domain_sql.leave_report_sql import (
    build_leave_sql_from_grounding,
    try_build_leave_detail_report_sql,
)
from app.services.ai_services.datamart.pipeline_common import validate_sql_with_grounding
from app.services.ai_services.datamart.domain_sql.report_spec import compile_report_spec
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_answer_adequacy import check_sql_answers_question
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings

LEAVE_Q = (
    "Generate a report of employees and their leave details by combining employee "
    "and leave transaction information. Include employee name, employee ID, branch, "
    "leave type, leave start date, leave end date, total leave days, and leave status. "
    "Display only approved leave requests"
)


def _screenshot_grounding() -> SchemaGrounding:
    """Typical failed UI turn: mart + dim + fact_leave_balance."""
    return SchemaGrounding(
        columns_by_table={
            "hr.fact_leave_balance": [
                "employee_sk",
                "source_emp_id",
                "leave_type_name",
                "period_label",
                "days_approved",
            ],
            "hr.dim_employee": [
                "employee_id",
                "employee_no",
                "full_name",
                "branch_name",
                "is_current",
            ],
            "hr.mart_employee_current": [
                "employee_id",
                "emp_no",
                "emp_fullname",
                "location_name",
                "designation_department",
            ],
        },
        source="test",
    )


def test_prefers_mart_when_it_has_display_columns():
    sql = build_leave_sql_from_grounding(LEAVE_Q, _screenshot_grounding())
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "emp_fullname" in sql
    assert "fact_leave_balance" in sql
    assert "dim_employee e" not in sql.replace("mart_employee_current", "")


def test_binding_passes_for_screenshot_grounding():
    g = _screenshot_grounding()
    sql = try_build_leave_detail_report_sql(LEAVE_Q, grounding=g)
    assert sql is not None
    assert validate_sql_bindings(sql, g) is None


def test_adequacy_passes_mart_plus_balance_not_dim_employee():
    """Regression: adequacy must not require dim_employee when mart is used."""
    g = _screenshot_grounding()
    sql = try_build_leave_detail_report_sql(LEAVE_Q, grounding=g)
    assert sql is not None
    spec = compile_report_spec(LEAVE_Q, chat_intent=ChatIntent.NEW_QUERY)
    err = check_sql_answers_question(
        question=LEAVE_Q,
        sql=sql,
        report_spec=spec,
    )
    assert err is None, err


def test_validate_sql_with_grounding_repairs_after_expand():
    g = _screenshot_grounding()
    bad_sql = (
        "SELECT e.emp_fullname AS employee_name, flb.days_approved "
        "FROM hr.dim_employee e "
        "JOIN hr.fact_leave_balance flb ON e.employee_id::text = flb.source_emp_id::text "
        "LIMIT 100"
    )

    def _no_retry(**_kwargs):
        return bad_sql, "", None, "should not call LLM"

    out = validate_sql_with_grounding(
        sql=bad_sql,
        narrative="",
        post_process_config=None,
        grounding=g,
        system_prompt="",
        retry_fn=_no_retry,
        allow_retry=False,
        question=LEAVE_Q,
        skip_llm_binding_retry=True,
    )
    assert out.error is None, out.error
    assert "mart_employee_current" in (out.sql or "") or "full_name" in (out.sql or "")
