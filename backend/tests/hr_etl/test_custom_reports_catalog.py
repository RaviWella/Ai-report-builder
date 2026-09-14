"""Tests for custom report catalog and sync validation."""
from __future__ import annotations

import pytest

from app.services.hr_etl.custom_reports_catalog import TenantCustomReportRow
from app.services.hr_etl.custom_reports_sync import (
    render_view_query,
    validate_view_query,
)


def test_render_view_query_substitutes_placeholders():
    rendered = render_view_query(
        "SELECT * FROM {mart_schema}.dim_employee WHERE tenant_id = '{tenant_id}'",
        "demo_tenant",
    )
    assert '"hr".dim_employee' in rendered or ".dim_employee" in rendered
    assert "demo_tenant" in rendered


def test_validate_view_query_rejects_ddl():
    with pytest.raises(ValueError, match="forbidden"):
        validate_view_query("SELECT delete FROM hr.dim_employee")


def test_validate_view_query_rejects_semicolons():
    with pytest.raises(ValueError, match="semicolons"):
        validate_view_query("SELECT 1; SELECT 2")


def test_validate_view_query_accepts_with_clause():
    validate_view_query(
        "WITH base AS (SELECT 1 AS n) SELECT n FROM base"
    )


def test_tenant_custom_report_row_needs_sync_when_sql_present():
    row = TenantCustomReportRow(
        id=1,
        tenant_id="demo_tenant",
        module="payroll",
        report_name="Test",
        view_name="vw_test",
        view_query="SELECT 1",
        report_type="table",
        source="sync",
        sort_order=0,
        is_active=True,
    )
    assert row.needs_sync is True

    empty_row = TenantCustomReportRow(
        id=2,
        tenant_id="demo_tenant",
        module="payroll",
        report_name="Empty",
        view_name="vw_empty",
        view_query=None,
        report_type="table",
        source="sync",
        sort_order=0,
        is_active=True,
    )
    assert empty_row.needs_sync is False
