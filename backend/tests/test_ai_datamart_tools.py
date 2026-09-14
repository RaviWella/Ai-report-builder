"""Safe read-only datamart tools the AI can call mid-conversation — pure
validation logic plus each tool's handler against a mocked connection (no
live datamart). Locks in: schema/table allowlisting, column-name validation,
the PII column blocklist (the tool that could return real per-employee
values is scoped to non-personal reference/category columns only, per
SRS §8.1 "the AI never receives row-level PII"), and best-effort
(never-raise) degradation.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.core.tenancy import TenantContext
from app.domain.enums import Role
from app.services.ai_datamart_tools import (
    _validate_schema_table,
    build_datamart_tools,
    query_table_columns,
)

_CTX = TenantContext(tenant_id="t", pg_schema="t", acting_user_id="u", role=Role.CLIENT_HR_ADMIN, on_behalf=False)


def _mock_conn(rows=None, columns=None):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    result = MagicMock()
    result.fetchall.return_value = rows or []
    result.fetchone.return_value = rows[0] if rows else None
    if columns is not None:
        result.keys.return_value = columns
        result.fetchmany.return_value = rows or []
    conn.execute.return_value = result
    return conn


@contextmanager
def _tools(conn):
    """Keeps the patches active for the whole `with` block, since a handler's
    own datamart_connection() call happens later, at await-time — not while
    building the tool closures."""
    with patch("app.services.ai_datamart_tools.resolve_datamart_key", return_value="dm"), \
         patch("app.services.ai_datamart_tools.datamart_connection") as dc:
        dc.return_value.__enter__.return_value = conn
        dc.return_value.__exit__.return_value = False
        yield {t.name: t for t in build_datamart_tools(_CTX, session_id="s1")}


def test_validate_schema_table_rejects_unknown_schema():
    assert _validate_schema_table("stg", "mart_employee") is not None


def test_validate_schema_table_rejects_non_reportable_table():
    assert _validate_schema_table("mart", "raw_dump") is not None


def test_validate_schema_table_accepts_mart_and_core_prefixes():
    assert _validate_schema_table("mart", "mart_employee") is None
    assert _validate_schema_table("core", "fct_overtime_day") is None
    assert _validate_schema_table("core", "dim_holiday_type") is None


@pytest.mark.asyncio
async def test_list_columns_rejects_disallowed_schema():
    with _tools(_mock_conn()) as tools:
        out = await tools["list_columns"].handler({"schema": "stg", "table": "s_overtime"})
    assert out.get("is_error") is True


@pytest.mark.asyncio
async def test_list_columns_returns_columns_for_allowed_table():
    conn = _mock_conn(rows=[("employee_no", "text"), ("ot_premium", "numeric")])
    with _tools(conn) as tools:
        out = await tools["list_columns"].handler({"schema": "core", "table": "fct_overtime_day"})
    assert out.get("is_error") is None
    assert "employee_no" in out["content"][0]["text"]


@pytest.mark.asyncio
async def test_sample_distinct_values_rejects_bad_column_name():
    with _tools(_mock_conn()) as tools:
        out = await tools["sample_distinct_values"].handler(
            {"schema": "core", "table": "fct_overtime_day", "column": "'; drop table x --"}
        )
    assert out.get("is_error") is True


@pytest.mark.asyncio
async def test_sample_distinct_values_rejects_unknown_column():
    conn = _mock_conn(rows=[])  # the existence check finds nothing
    with _tools(conn) as tools:
        out = await tools["sample_distinct_values"].handler(
            {"schema": "core", "table": "fct_overtime_day", "column": "no_such_column"}
        )
    assert out.get("is_error") is True


@pytest.mark.asyncio
async def test_sample_distinct_values_blocks_pii_looking_columns():
    with _tools(_mock_conn()) as tools:
        out = await tools["sample_distinct_values"].handler(
            {"schema": "mart", "table": "mart_employee", "column": "employee_name"}
        )
    assert out.get("is_error") is True


@pytest.mark.asyncio
async def test_sample_distinct_values_blocks_salary_column_without_hitting_the_db():
    conn = _mock_conn()
    with _tools(conn) as tools:
        out = await tools["sample_distinct_values"].handler(
            {"schema": "mart", "table": "mart_employee", "column": "basic_salary"}
        )
    assert out.get("is_error") is True
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sample_distinct_values_allows_non_pii_category_column():
    conn = _mock_conn(rows=[("ANNUAL", 12), ("SICK", 3)])
    with _tools(conn) as tools:
        out = await tools["sample_distinct_values"].handler(
            {"schema": "core", "table": "dim_holiday_type", "column": "holiday_type"}
        )
    assert out.get("is_error") is None


def test_query_table_columns_returns_name_and_type():
    # The plain function `list_columns` (the MCP tool) AND the `/ai/source-columns`
    # REST route both delegate to — reused so the builder's field pickers get the
    # exact same introspection the AI chat's own tool already uses.
    conn = _mock_conn(rows=[("employee_no", "text"), ("work_date", "date")])
    with patch("app.services.ai_datamart_tools.datamart_connection") as dc:
        dc.return_value.__enter__.return_value = conn
        dc.return_value.__exit__.return_value = False
        cols = query_table_columns(_CTX, "dm", "mart", "mart_attendance_daily")
    assert cols == [{"column": "employee_no", "type": "text"}, {"column": "work_date", "type": "date"}]


def test_query_table_columns_propagates_a_db_failure():
    # Unlike the MCP tool (which degrades to an error result), this is a plain
    # function — callers (the REST route) decide how to surface a failure.
    with patch("app.services.ai_datamart_tools.datamart_connection", side_effect=RuntimeError("no VPN")), \
         pytest.raises(RuntimeError):
        query_table_columns(_CTX, "dm", "mart", "mart_attendance_daily")


@pytest.mark.asyncio
async def test_a_db_failure_degrades_to_an_error_result_not_a_raised_exception():
    with patch("app.services.ai_datamart_tools.resolve_datamart_key", return_value="dm"), \
         patch("app.services.ai_datamart_tools.datamart_connection", side_effect=RuntimeError("no VPN")):
        tools = {t.name: t for t in build_datamart_tools(_CTX, session_id="s1")}
        out = await tools["list_columns"].handler({"schema": "mart", "table": "mart_employee"})
    assert out.get("is_error") is True  # never raises into the SDK's tool-call loop
