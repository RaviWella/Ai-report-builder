"""Tests for structured grounded schema LLM prompts."""
from app.services.ai_services.datamart.prompts.grounded_schema_prompt import (
    build_validated_join_lines,
    format_grounded_schema_for_llm,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.semantic.semantic_layer import SemanticResolution


def test_format_groups_tables_by_schema_and_index():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_headcount": ["employee_id", "basic_salary", "designation"],
            "hr.mart_employee_current": ["employee_no", "emp_fullname", "employee_sk"],
        },
        source="test",
    )
    text = format_grounded_schema_for_llm(grounding)
    assert "=== GROUNDED WAREHOUSE SCHEMA ===" in text
    assert "--- SCHEMA: hr_semantic ---" in text
    assert "--- SCHEMA: hr ---" in text
    assert "TABLE: hr_semantic.vw_headcount" in text
    assert "TABLE: hr.mart_employee_current" in text
    assert "[T1]" in text and "[T2]" in text
    assert "employee_id" in text
    assert "employee_no" in text
    assert "Rules:" in text
    assert "VALID JOIN PATHS" in text


def test_semantic_mappings_scoped_per_table():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.dim_employee": ["employee_id", "emp_fullname"],
            "hr.mart_employee_current": ["employee_no", "emp_fullname"],
        },
        dimension_bindings=[
            ("employee_id", "dim_employee", "employee_id"),
            ("employee_name", "mart_employee_current", "emp_fullname"),
        ],
        source="test",
    )
    semantics = SemanticResolution(
        dimension_bindings=grounding.dimension_bindings,
        topics_matched=["workforce"],
    )
    text = format_grounded_schema_for_llm(grounding, semantics=semantics)
    assert "BUSINESS TERMS" in text
    assert "[hr.dim_employee]" in text
    assert "[hr.mart_employee_current]" in text
    assert '"employee name" → emp_fullname' in text


def test_catalog_join_skips_missing_columns():
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": ["employee_no", "emp_fullname", "employee_sk"],
            "hr.dim_employee": ["employee_sk", "emp_fullname"],
        },
        source="test",
    )
    lines = build_validated_join_lines(grounding)
    joined = "\n".join(lines)
    assert "employee_sk" in joined or "employee_no" in joined
    assert "mart_employee_current" in joined.lower() or "dim_employee" in joined.lower()
