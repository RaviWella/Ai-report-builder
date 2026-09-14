"""Warehouse SQL execution guards."""
from app.services.ai_services.datamart.sql.sql_exec_guard import (
    ensure_select_limit,
    is_warehouse_timeout_error,
)


def test_ensure_select_limit_appends_when_missing():
    sql = "SELECT 1 AS x"
    out = ensure_select_limit(sql, max_rows=100)
    assert "LIMIT 100" in out.upper()


def test_ensure_select_limit_clamps_high_limit():
    sql = "SELECT 1 LIMIT 9999"
    out = ensure_select_limit(sql, max_rows=500)
    assert out.upper().endswith("LIMIT 500")


def test_is_warehouse_timeout_error():
    assert is_warehouse_timeout_error("canceling statement due to statement timeout")
    assert not is_warehouse_timeout_error("relation foo does not exist")
