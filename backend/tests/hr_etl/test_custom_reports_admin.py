"""Tests for custom report admin service validation."""
from __future__ import annotations

import pytest

from app.services.hr_etl.custom_reports_admin import row_to_out
from app.services.hr_etl.custom_reports_catalog import TenantCustomReportRow


def test_row_to_out_maps_catalog_row():
    row = TenantCustomReportRow(
        id=1,
        tenant_id="demo_tenant",
        module="payroll",
        report_name="Test Report",
        view_name="vw_test",
        view_query="SELECT 1",
        report_type="table",
        source="sync",
        sort_order=10,
        is_active=True,
        is_system=False,
    )
    out = row_to_out(row)
    assert out.report_name == "Test Report"
    assert out.source == "sync"


@pytest.mark.parametrize(
    "query",
    [
        "SELECT delete FROM hr.dim_employee",
        "DROP TABLE hr.dim_employee",
    ],
)
def test_validate_view_query_rejects_unsafe_sql(query: str):
    from app.services.hr_etl.custom_reports_sync import validate_view_query

    with pytest.raises(ValueError):
        validate_view_query(query)
