"""Leave report when fact_leave_transaction is not deployed."""
from app.services.ai_services.datamart.domain_sql.leave_report_sql import try_build_leave_detail_report_sql
from app.services.ai_services.datamart.validation.report_spec_validate import validate_retrieval_for_spec
from app.services.ai_services.datamart.domain_sql.report_spec import (
    ReportDomain,
    ReportSpec,
    ReportType,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding

LEAVE_Q = (
    "Generate a report of employees and their leave details. "
    "Display only approved leave requests"
)


def test_retrieval_allows_balance_without_transaction_tables():
    spec = ReportSpec(
        domain=ReportDomain.LEAVE,
        report_type=ReportType.DETAIL_LIST,
        required_tables=["fact_leave_transaction", "dim_leave_type", "dim_employee"],
    )
    err = validate_retrieval_for_spec(
        spec,
        ["fact_leave_balance", "dim_employee"],
    )
    assert err is None


def test_leave_sql_from_balance_grounding():
    g = SchemaGrounding(
        columns_by_table={
            "hr.fact_leave_balance": [
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
        },
        source="test",
    )
    sql = try_build_leave_detail_report_sql(LEAVE_Q, grounding=g)
    assert sql is not None
    assert "fact_leave_balance" in sql
    assert "fact_leave_transaction" not in sql
