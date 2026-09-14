"""Repair shift join type errors from LLM / add-scenario SQL."""
from app.services.ai_services.datamart.sql.sql_exec_repairs import repair_integer_text_join_cast


def test_repair_shift_id_to_shift_sk_uses_source_shift_id():
    sql = """
SELECT e.emp_no, e.emp_fullname, s.shift_name
FROM hr.dim_employee e
LEFT JOIN hr.dim_shift s ON e.shift_id = s.shift_sk
WHERE e.is_current IS TRUE
LIMIT 500;
"""
    err = (
        'psycopg2.errors.UndefinedFunction: operator does not exist: integer = text\n'
        "LINE 3: LEFT JOIN hr.dim_shift s ON e.shift_id = s.shift_sk"
    )
    fixed = repair_integer_text_join_cast(sql, err)
    assert fixed is not None
    assert "source_shift_id::text = e.shift_id::text" in fixed
    assert "shift_sk" not in fixed


def test_repair_casts_shift_id_join_without_sk():
    sql = "SELECT 1 FROM hr.mart_employee_current m JOIN hr.dim_shift s ON m.shift_id = s.source_shift_id"
    err = "UndefinedFunction operator does not exist: integer = text"
    fixed = repair_integer_text_join_cast(sql, err)
    assert fixed is not None
    assert "::text" in fixed


def test_repair_shift_sk_on_left_side():
    sql = """
SELECT mec.emp_no, ds.shift_name
FROM hr.mart_employee_current mec
JOIN hr.dim_shift ds ON ds.shift_sk = mec.shift_id
LIMIT 500
"""
    err = (
        "UndefinedFunction operator does not exist: text = integer "
        "LINE 7: ON ds.shift_sk = mec.shift_id"
    )
    fixed = repair_integer_text_join_cast(sql, err)
    assert fixed is not None
    assert "ds.source_shift_id::text = mec.shift_id::text" in fixed
    assert "shift_sk" not in fixed
