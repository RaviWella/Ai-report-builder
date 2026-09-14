"""GET /ai/source-columns — powers the Rule Report builder's Filters/Add-
column pickers for a single-`source` spec (the shape that previously had no
column list at all, forcing blind typing where the Excel Upload panel's
field picker already lets you pick from a list). Route handlers are plain
functions here (no TestClient in this repo's test style) — call directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.ai import source_columns
from app.core.tenancy import TenantContext
from app.domain.enums import Role

_CTX = TenantContext(tenant_id="t", pg_schema="t", acting_user_id="u", role=Role.CLIENT_HR_ADMIN, on_behalf=False)


def _mock_conn(rows):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    result = MagicMock()
    result.fetchall.return_value = rows
    conn.execute.return_value = result
    return conn


def test_a_single_source_string_returns_its_columns():
    conn = _mock_conn([("employee_no", "text"), ("work_date", "date")])
    with patch("app.services.ai_datamart_tools.resolve_datamart_key", return_value="dm"), \
         patch("app.services.ai_datamart_tools.datamart_connection") as dc:
        dc.return_value.__enter__.return_value = conn
        dc.return_value.__exit__.return_value = False
        out = source_columns("mart.mart_attendance_daily", ctx=_CTX)
    assert out == {"columns": [{"column": "employee_no", "type": "text"}, {"column": "work_date", "type": "date"}]}


def test_a_disallowed_schema_is_a_clean_400_not_a_db_call():
    with patch("app.services.ai_datamart_tools.datamart_connection") as dc, \
         pytest.raises(HTTPException) as exc:
        source_columns("stg.raw_dump", ctx=_CTX)
    assert exc.value.status_code == 400
    dc.assert_not_called()


def test_a_db_failure_is_a_clean_502():
    with patch("app.services.ai_datamart_tools.resolve_datamart_key", return_value="dm"), \
         patch("app.services.ai_datamart_tools.datamart_connection", side_effect=RuntimeError("no VPN")), \
         pytest.raises(HTTPException) as exc:
        source_columns("mart.mart_attendance_daily", ctx=_CTX)
    assert exc.value.status_code == 502
