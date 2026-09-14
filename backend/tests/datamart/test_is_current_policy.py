"""Tests for SCD is_current row-version policy."""
from __future__ import annotations

from app.services.ai_services.datamart.postprocess.is_current_policy import (
    VersionRowIntent,
    apply_is_current_policy,
    classify_version_row_intent,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding


def _grounding(*tables: tuple[str, list[str]]) -> SchemaGrounding:
    cols = {f"hr.{name}": columns for name, columns in tables}
    return SchemaGrounding(columns_by_table=cols, source="test")


def test_classify_current_by_default():
    assert classify_version_row_intent("list active employees") == VersionRowIntent.CURRENT_ONLY


def test_classify_history_intent():
    assert (
        classify_version_row_intent("show salary history for each employee")
        == VersionRowIntent.HISTORY_ALLOWED
    )


def test_injects_filter_for_versioned_dim():
    sql = (
        "SELECT e.emp_fullname FROM hr.dim_employee e "
        "WHERE e.emp_status = 'active' LIMIT 100"
    )
    g = _grounding(("dim_employee", ["employee_id", "emp_fullname", "is_current", "emp_status"]))
    out, changed = apply_is_current_policy(
        sql,
        question="active employees",
        grounding=g,
    )
    assert changed
    assert "e.is_current IS TRUE" in out
    assert "emp_status = 'active'" in out


def test_skips_when_predicate_present():
    sql = (
        "SELECT e.emp_fullname FROM hr.dim_employee e "
        "WHERE e.is_current = TRUE AND e.emp_status = 'active' LIMIT 100"
    )
    g = _grounding(("dim_employee", ["employee_id", "is_current"]))
    out, changed = apply_is_current_policy(sql, question="employees", grounding=g)
    assert not changed
    assert out == sql


def test_skips_for_history_question():
    sql = "SELECT e.emp_fullname FROM hr.dim_employee e LIMIT 100"
    g = _grounding(("dim_employee", ["employee_id", "is_current"]))
    out, changed = apply_is_current_policy(
        sql,
        question="employment history over time",
        grounding=g,
    )
    assert not changed


def test_multiple_versioned_tables():
    sql = (
        "SELECT e.emp_fullname, d.designation_name "
        "FROM hr.dim_employee e "
        "JOIN hr.dim_designation d ON e.designation_sk = d.designation_sk "
        "LIMIT 50"
    )
    g = _grounding(
        ("dim_employee", ["employee_id", "is_current", "designation_sk"]),
        ("dim_designation", ["designation_sk", "designation_name", "is_current"]),
    )
    out, changed = apply_is_current_policy(sql, question="employee titles", grounding=g)
    assert changed
    assert "e.is_current IS TRUE" in out
    assert "d.is_current IS TRUE" in out


def test_skips_non_versioned_table():
    sql = "SELECT m.employee_id FROM hr.mart_employee_current m LIMIT 10"
    g = _grounding(("mart_employee_current", ["employee_id", "emp_fullname"]))
    out, changed = apply_is_current_policy(sql, question="headcount", grounding=g)
    assert not changed
