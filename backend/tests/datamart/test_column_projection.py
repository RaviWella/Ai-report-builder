"""Column projection rules for datamart SQL generation."""
from __future__ import annotations

from app.services.ai_services.datamart.semantic.column_projection import (
    is_join_only_column,
    partition_columns,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_faithfulness import check_sql_faithfulness


def test_surrogate_keys_are_join_only():
    cols = ["employee_sk", "employee_no", "full_name", "designation_sk", "designation_name"]
    assert is_join_only_column("employee_sk", cols)
    assert is_join_only_column("designation_sk", cols)
    assert not is_join_only_column("employee_no", cols)
    assert not is_join_only_column("full_name", cols)
    assert not is_join_only_column("designation_name", cols)


def test_fk_hidden_when_display_name_exists():
    cols = ["employee_id", "employee_no", "emp_fullname", "branch"]
    assert is_join_only_column("employee_id", cols)
    assert not is_join_only_column("branch", cols)


def test_employee_id_allowed_when_no_display_alternative():
    cols = ["employee_id", "hire_date"]
    assert not is_join_only_column("employee_id", cols)


def test_partition_columns_splits_lists():
    cols = ["employee_sk", "employee_no", "designation_name", "tenant_id"]
    display, join_only = partition_columns(cols)
    assert display == ["employee_no", "designation_name"]
    assert join_only == ["employee_sk", "tenant_id"]


def test_faithfulness_warns_on_projected_join_key():
    sql = """
    SELECT e.employee_sk, e.full_name
    FROM hr.dim_employee e
    LIMIT 50
    """
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.dim_employee": [
                "employee_sk",
                "employee_no",
                "full_name",
                "employee_id",
            ],
        }
    )
    result = check_sql_faithfulness(
        question="List employees with name",
        sql=sql,
        grounding=grounding,
        schema_links=[],
        binding_passed=True,
    )
    assert any("join key" in w.lower() for w in result.warnings)
