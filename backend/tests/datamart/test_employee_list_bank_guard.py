"""Employee list template must not steal bank-detail questions."""
from app.services.ai_services.datamart.domain_sql.employee_list_sql import try_build_employee_list_sql
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def _mart_only_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "employee_category",
                "is_current",
            ],
        },
        source="test",
    )


def test_employee_list_skips_bank_detail_questions():
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    assert try_build_employee_list_sql(q, grounding=_mart_only_grounding()) is None
