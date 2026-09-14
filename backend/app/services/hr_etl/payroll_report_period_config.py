"""Payroll-area custom report period filtering (preview) — driven by tenant catalog."""
from __future__ import annotations

from dataclasses import dataclass

_DEFAULT_YEAR_COLUMN = "proc_year"
_DEFAULT_MONTH_COLUMN = "proc_month"


@dataclass(frozen=True)
class PayrollPeriodFilterSpec:
    year_column: str = _DEFAULT_YEAR_COLUMN
    month_column: str = _DEFAULT_MONTH_COLUMN


def payroll_period_filter_spec(
    view_name: str,
    *,
    tenant_id: str | None = None,
) -> PayrollPeriodFilterSpec | None:
    if tenant_id:
        from app.services.hr_etl.custom_reports_catalog import get_report_definition_sync

        definition = get_report_definition_sync(tenant_id, view_name)
        if definition is not None:
            year_col = (definition.period_year_column or "").strip()
            month_col = (definition.period_month_column or "").strip()
            if year_col and month_col:
                return PayrollPeriodFilterSpec(year_col, month_col)
            if definition.is_payslip:
                return None
            return None
    return None


def supports_payroll_period_filter(
    view_name: str,
    *,
    tenant_id: str | None = None,
) -> bool:
    return payroll_period_filter_spec(view_name, tenant_id=tenant_id) is not None


def payroll_period_columns_to_omit(
    view_name: str,
    *,
    tenant_id: str | None = None,
) -> frozenset[str]:
    spec = payroll_period_filter_spec(view_name, tenant_id=tenant_id)
    if spec is None:
        return frozenset()
    return frozenset({spec.year_column.lower(), spec.month_column.lower()})
