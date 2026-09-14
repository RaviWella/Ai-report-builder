"""Deterministic SQL repairs after execution errors."""
from app.services.ai_services.datamart.sql.sql_exec_repairs import try_repair_sql_execution_error

_BAD_LEAVE_SQL = """
SELECT e.full_name, lt.leave_type_name
FROM public_mint_audit.dim_employee e
JOIN public_mint_audit.fact_leave_transaction lt ON e.employee_id = lt.employee_id
JOIN public_mint_audit.dim_leave_type lt ON lt.leave_type_id = lt.leave_type_id
WHERE lt.leave_status_name = 'Approved'
LIMIT 500
"""

_ERROR = (
    'psycopg2.errors.UndefinedFunction: operator does not exist: integer = text\n'
    "LINE 17: ON lt.leave_type_id = lt.leave_type_id"
)


def test_repair_leave_duplicate_alias():
    fixed = try_repair_sql_execution_error(_BAD_LEAVE_SQL, _ERROR)
    assert fixed is not None
    assert "dim_leave_type dlt" in fixed.lower()
    assert "fact_leave_transaction flt" in fixed.lower()
    assert "flt.leave_type_id::text = dlt.leave_type_id::text" in fixed
    assert " ON lt.leave_type_id = lt.leave_type_id" not in fixed
    assert "dlt.leave_type_name" in fixed


def test_repair_undefined_column_status_on_leave_fact():
    sql = (
        "SELECT e.full_name, flt.leave_date, flt.status, dlt.leave_type_name "
        "FROM public_mint_audit.fact_leave_transaction flt "
        "JOIN public_mint_audit.dim_employee e ON e.employee_id = flt.employee_id "
        "JOIN public_mint_audit.dim_leave_type dlt "
        "ON flt.leave_type_id::text = dlt.leave_type_id::text LIMIT 500"
    )
    err = '(psycopg2.errors.UndefinedColumn) column flt.status does not exist'
    fixed = try_repair_sql_execution_error(sql, err)
    assert fixed is not None
    assert "flt.leave_status_name" in fixed
    assert "flt.status" not in fixed


def test_repair_designation_sk_integer_text_cast():
    sql = """
SELECT e.emp_fullname
FROM hr.mart_employee_current e
JOIN hr.dim_employee d ON e.employee_sk = d.employee_sk
JOIN hr.dim_designation des ON d.source_desig_id = des.designation_sk
LIMIT 10
"""
    err = "UndefinedFunction: operator does not exist: integer = text LINE 14: ON d.source_desig_id = des.designation_sk"
    fixed = try_repair_sql_execution_error(sql, err)
    assert fixed is not None
    assert "source_desig_id = des.source_desig_id" in fixed


def test_repair_mart_employee_designation_name_unqualified():
    sql = (
        "SELECT emp_fullname, designation_name AS designation, basic_salary "
        "FROM hr.mart_employee_current ORDER BY basic_salary DESC LIMIT 10"
    )
    err = '(psycopg2.errors.UndefinedColumn) column "designation_name" does not exist'
    fixed = try_repair_sql_execution_error(sql, err)
    assert fixed is not None
    assert "designation AS designation" in fixed or "designation," in fixed
    assert "designation_name" not in fixed


def test_repair_leave_type_cast_only():
    sql = """
SELECT a.id FROM public_mint_audit.fact_leave_transaction f
JOIN public_mint_audit.dim_leave_type d ON f.leave_type_id = d.leave_type_id
"""
    err = "UndefinedFunction: operator does not exist: integer = text"
    fixed = try_repair_sql_execution_error(sql, err)
    assert fixed is not None
    assert "leave_type_id::text" in fixed
