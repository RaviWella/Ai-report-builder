"""Tests for deterministic employee + bank detail SQL template."""
from app.services.ai_services.datamart.domain_sql.employee_bank_detail_sql import (
    looks_like_employee_bank_detail_report,
    try_build_employee_bank_detail_sql,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def _bank_grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "employee_category",
                "employee_sk",
                "is_current",
            ],
            "hr.fct_salary_bank_instruction": [
                "employee_sk",
                "source_bank_id",
                "bank_passbook_name",
            ],
            "hr.dim_bank": ["source_bank_id", "bank_name", "bank_code"],
        },
        source="test",
    )


def test_detects_employee_bank_list_question():
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    g = _bank_grounding()
    assert looks_like_employee_bank_detail_report(q, grounding=g)


def test_builds_mart_bank_join_sql():
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    sql = try_build_employee_bank_detail_sql(q, grounding=_bank_grounding())
    assert sql is not None
    assert "mart_employee_current" in sql
    assert "fct_salary_bank_instruction" in sql
    assert "dim_bank" in sql
    assert "emp_no AS employee_number" in sql
    assert "employee_category" in sql
    assert "bank_name" in sql
    assert "NULL::text" not in sql


def test_builds_bank_sql_from_dim_employee_when_fact_missing():
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "employee_category",
                "employee_sk",
            ],
            "hr.dim_employee": [
                "employee_sk",
                "bank_name",
                "branch_name",
            ],
            "hr.dim_bank": ["bank_name", "bank_code"],
        },
        source="test",
    )
    sql = try_build_employee_bank_detail_sql(q, grounding=grounding)
    assert sql is not None
    assert "dim_employee" in sql
    assert "bank_name" in sql
