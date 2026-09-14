"""Join semantics validation and repair."""
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_join_semantics import (
    try_repair_join_semantics,
    validate_join_semantics,
)


def _grounding(*tables: tuple[str, list[str]]) -> SchemaGrounding:
    cols = {f"hr.{t}": c for t, c in tables}
    return SchemaGrounding(columns_by_table=cols)


def test_validate_rejects_designation_text_to_designation_sk():
    g = _grounding(
        ("mart_employee_current", ["emp_no", "emp_fullname", "designation", "employee_sk"]),
        ("dim_designation", ["designation_sk", "designation_name", "source_desig_id"]),
        ("mart_cost_to_company", ["employee_sk", "basic_salary"]),
    )
    sql = """
SELECT mec.emp_no, des.designation_name, mct.basic_salary
FROM hr.mart_employee_current mec
JOIN hr.mart_cost_to_company mct ON mec.employee_sk = mct.employee_sk
JOIN hr.dim_designation des ON mec.designation::text = des.designation_sk::text
ORDER BY mct.basic_salary DESC
LIMIT 10
"""
    err = validate_join_semantics(sql, g)
    assert err is not None
    assert "designation" in err.lower()
    assert "designation_sk" in err.lower() or "key" in err.lower()


def test_repair_removes_bad_designation_join():
    g = _grounding(
        ("mart_employee_current", ["emp_no", "emp_fullname", "designation", "employee_sk"]),
        ("dim_designation", ["designation_sk", "designation_name", "source_desig_id"]),
        ("mart_cost_to_company", ["employee_sk", "basic_salary"]),
    )
    sql = """
SELECT mec.emp_no, des.designation_name AS job_title, mct.basic_salary
FROM hr.mart_employee_current mec
JOIN hr.mart_cost_to_company mct ON mec.employee_sk = mct.employee_sk
JOIN hr.dim_designation des ON mec.designation::text = des.designation_sk::text
ORDER BY mct.basic_salary DESC
LIMIT 10
"""
    fixed = try_repair_join_semantics(sql, g)
    assert fixed is not None
    assert "dim_designation" not in fixed.lower()
    assert "mec.designation" in fixed.lower()
    assert validate_join_semantics(fixed, g) is None


def test_validate_allows_employee_sk_join():
    g = _grounding(
        ("mart_employee_current", ["employee_sk", "emp_fullname"]),
        ("mart_cost_to_company", ["employee_sk", "basic_salary"]),
    )
    sql = """
SELECT mec.emp_fullname, mct.basic_salary
FROM hr.mart_employee_current mec
JOIN hr.mart_cost_to_company mct ON mec.employee_sk = mct.employee_sk
LIMIT 10
"""
    assert validate_join_semantics(sql, g) is None
