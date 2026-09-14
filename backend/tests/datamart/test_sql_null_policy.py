"""NULL row filtering policy for generated SQL."""
from app.services.ai_services.datamart.sql.sql_null_policy import (
    apply_null_row_policy,
    classify_null_row_intent,
)


def test_classify_skips_when_user_wants_null():
    assert classify_null_row_intent("employees without a manager").name == "INCLUDE_OR_NULL_FOCUS"


def test_order_by_adds_is_not_null():
    sql = (
        "SELECT emp_fullname, designation_name AS designation, basic_salary "
        "FROM hr.mart_employee_current m ORDER BY m.basic_salary DESC LIMIT 10"
    )
    q = "Show me the top 10 highest paid employees"
    out, changed = apply_null_row_policy(sql, question=q)
    assert changed
    assert "m.basic_salary IS NOT NULL" in out


def test_skips_when_user_asks_include_null():
    sql = "SELECT x FROM t ORDER BY x.salary DESC"
    out, changed = apply_null_row_policy(sql, question="include null salary values")
    assert not changed
    assert out == sql


def test_name_filter_for_employee_list():
    sql = (
        "SELECT m.emp_fullname, m.basic_salary FROM hr.mart_employee_current m "
        "ORDER BY m.emp_fullname LIMIT 500"
    )
    out, changed = apply_null_row_policy(sql, question="List all employees")
    assert changed
    assert "emp_fullname IS NOT NULL" in out
