"""Tests for custom report export formatting."""
from __future__ import annotations

from app.services.hr_etl.custom_reports_data import (
    _EXPORT_BRAND_FOOTER,
    _export_column_label,
    _export_generated_at,
    _format_amount_display,
    _is_amount_column,
)


def test_export_column_label_replaces_underscores_and_title_cases():
    assert _export_column_label("emp_no") == "Emp No"
    assert _export_column_label("proc_year") == "Year"
    assert _export_column_label("proc_month") == "Month"
    assert _export_column_label("employee_name") == "Employee Name"


def test_export_column_label_handles_single_word():
    assert _export_column_label("amount") == "Amount"


def test_export_column_label_preserves_report_acronyms():
    assert _export_column_label("ot_1_5_hours") == "OT 1 5 Hours"
    assert _export_column_label("total_ot_amount") == "Total OT Amount"
    assert _export_column_label("sum_of_ot") == "Sum Of OT"
    assert _export_column_label("je") == "JE"


def test_amount_column_detection_and_formatting():
    assert _is_amount_column("basic_salary")
    assert _is_amount_column("total_ot_amount")
    assert not _is_amount_column("proc_year")
    assert _format_amount_display(10000) == "10,000.00"
    assert _format_amount_display(1234.5) == "1,234.50"


def test_export_branding_constants():
    assert _EXPORT_BRAND_FOOTER == "Powered by MintHRM"
    assert "UTC" in _export_generated_at()
