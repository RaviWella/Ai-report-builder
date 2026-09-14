"""Deterministic SQL fast path (no LLM)."""
from app.services.ai_services.datamart.domain_sql.report_spec import compile_report_spec
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_fast_path import (
    rewrite_hallucinated_table_names,
    try_resolve_deterministic_sql,
)


def _grounding_with_bank_tables() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr_semantic.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "employee_category",
                "employee_sk",
                "is_current",
            ],
            "hr_semantic.fct_salary_bank_instruction": [
                "employee_sk",
                "source_bank_id",
                "bank_passbook_name",
            ],
            "hr_semantic.dim_bank": ["bank_sk", "bank_name", "bank_code"],
        },
        source="test",
    )


def test_fast_path_employee_bank_before_llm():
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    grounding = _grounding_with_bank_tables()
    resolved = try_resolve_deterministic_sql(q, grounding=grounding)
    assert resolved is not None
    sql, source, _narr = resolved
    assert source == "employee_bank_detail_template"
    assert "mart_employee_current" in sql
    assert "fct_salary_bank_instruction" in sql


def test_report_spec_routes_employee_bank_template():
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    spec = compile_report_spec(q)
    assert spec.template_id == "workforce.employee_bank_detail"
    assert spec.domain.value == "workforce"


def test_rewrite_vw_employee_hallucination():
    grounding = _grounding_with_bank_tables()
    sql = "SELECT * FROM hr_semantic.vw_employee e LIMIT 10;"
    fixed = rewrite_hallucinated_table_names(sql, grounding)
    assert "mart_employee_current" in fixed
    assert "vw_employee" not in fixed.lower()
