"""Tests for payroll custom report period filter (tenant catalog driven)."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from app.services.hr_etl.custom_reports_catalog import TenantCustomReportRow
from app.services.hr_etl.custom_reports_data import ExportFilters, _build_view_where
from app.services.hr_etl.payroll_report_period_config import (
    payroll_period_columns_to_omit,
    payroll_period_filter_spec,
    supports_payroll_period_filter,
)


def _definition(
    view_name: str,
    *,
    report_type: str = "table",
    year_col: str | None = "proc_year",
    month_col: str | None = "proc_month",
) -> TenantCustomReportRow:
    return TenantCustomReportRow(
        id=1,
        tenant_id="demo_tenant",
        module="payroll",
        report_name="Test",
        view_name=view_name,
        view_query="SELECT 1",
        report_type=report_type,  # type: ignore[arg-type]
        source="sync",
        sort_order=10,
        is_active=True,
        is_system=True,
        period_year_column=year_col,
        period_month_column=month_col,
    )


@patch(
    "app.services.hr_etl.custom_reports_catalog.get_report_definition_sync",
    return_value=_definition(
        "vw_statutory_remittance_by_month",
        year_col="reporting_year",
        month_col="reporting_month",
    ),
)
def test_statutory_remittance_uses_reporting_columns(_mock_get):
    spec = payroll_period_filter_spec(
        "vw_statutory_remittance_by_month", tenant_id="demo_tenant"
    )
    assert spec is not None
    assert spec.year_column == "reporting_year"
    assert spec.month_column == "reporting_month"


@patch(
    "app.services.hr_etl.custom_reports_catalog.get_report_definition_sync",
    return_value=_definition("vw_employee_ot_worksheet"),
)
def test_default_payroll_reports_use_proc_columns(_mock_get):
    spec = payroll_period_filter_spec(
        "vw_employee_ot_worksheet", tenant_id="demo_tenant"
    )
    assert spec is not None
    assert spec.year_column == "proc_year"
    assert spec.month_column == "proc_month"


@patch(
    "app.services.hr_etl.custom_reports_catalog.get_report_definition_sync",
    return_value=_definition(
        "vw_employee_payslip_vertical",
        report_type="payslip",
        year_col=None,
        month_col=None,
    ),
)
def test_payslip_has_no_period_filter(_mock_get):
    assert not supports_payroll_period_filter(
        "vw_employee_payslip_vertical", tenant_id="demo_tenant"
    )


@patch(
    "app.services.hr_etl.custom_reports_catalog.get_report_definition_sync",
    return_value=_definition(
        "vw_statutory_remittance_by_month",
        year_col="reporting_year",
        month_col="reporting_month",
    ),
)
def test_period_columns_omitted_from_column_filters(_mock_get):
    omitted = payroll_period_columns_to_omit(
        "vw_statutory_remittance_by_month", tenant_id="demo_tenant"
    )
    assert omitted == frozenset({"reporting_year", "reporting_month"})


@patch(
    "app.services.hr_etl.custom_reports_catalog.get_report_definition_sync",
    return_value=_definition(
        "vw_statutory_remittance_by_month",
        year_col="reporting_year",
        month_col="reporting_month",
    ),
)
def test_build_view_where_applies_catalog_columns(_mock_get):
    filters = ExportFilters(proc_year=2025, proc_month=3)
    where_sql, params = _build_view_where(
        "vw_statutory_remittance_by_month",
        filters,
        {"reporting_year", "reporting_month", "payment_type"},
        tenant_id="demo_tenant",
    )
    assert '"reporting_year" = :proc_year' in where_sql
    assert '"reporting_month" = :proc_month' in where_sql
    assert params["proc_year"] == 2025
    assert params["proc_month"] == 3


def test_build_view_where_rejects_unknown_report():
    filters = ExportFilters(proc_year=2025, proc_month=3)
    with pytest.raises(ValueError, match="not supported"):
        _build_view_where(
            "vw_unknown_report",
            filters,
            {"proc_year", "proc_month"},
            tenant_id="demo_tenant",
        )
