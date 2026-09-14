"""Pivoted (wide) report — reshapes a LONG rule-report result (one row per
e.g. employee+date) into a WIDE grid (one row per employee, one column per
distinct date/dimension value actually present) plus per-cell status color
in the Excel/PDF exports. See PivotSpec (app/domain/report_spec.py) and
report_service._apply_pivot.
"""

from __future__ import annotations

import datetime
import io

import openpyxl

from app.domain.report_spec import ColumnPresentation, PivotSpec, PresentationSpec
from app.query_engine.runner import QueryResult
from app.rendering.excel_renderer import render_excel
from app.services.report_service import _apply_pivot

_LONG_ROWS = [
    {"employee_no": "284", "name": "Peter Mark", "work_date": datetime.date(2026, 8, 1),
     "hours": 8, "status": "Present"},
    {"employee_no": "284", "name": "Peter Mark", "work_date": datetime.date(2026, 8, 2),
     "hours": 4, "status": "Half Day"},
    {"employee_no": "333", "name": "Jonathan Peezer", "work_date": datetime.date(2026, 8, 1),
     "hours": 8, "status": "Present"},
    {"employee_no": "333", "name": "Jonathan Peezer", "work_date": datetime.date(2026, 8, 2),
     "hours": 0, "status": "Absent"},
]
_LONG_COLUMNS = ["employee_no", "name", "work_date", "hours", "status"]
_PIVOT = {
    "column_field": "work_date", "value_field": "hours", "status_field": "status",
    "column_label_format": "%d %b",
}


def test_pivot_reshapes_long_rows_into_one_row_per_identity():
    rows, columns = _apply_pivot(_LONG_ROWS, _LONG_COLUMNS, _PIVOT)
    assert columns == ["employee_no", "name", "01 Aug", "02 Aug"]
    assert len(rows) == 2
    peter = next(r for r in rows if r["employee_no"] == "284")
    assert peter["01 Aug"] == 8
    assert peter["02 Aug"] == 4
    jonathan = next(r for r in rows if r["employee_no"] == "333")
    assert jonathan["01 Aug"] == 8
    assert jonathan["02 Aug"] == 0


def test_pivot_backfills_a_missing_cell_with_none_not_a_missing_key():
    # Real production crash: an employee with no row for a given date (e.g.
    # joined mid-range) used to leave that column's key OFF the row entirely,
    # which broke the renderers' cell lookup and could surface `_cell_status`
    # (a dict) as a cell's "value" — "Unsupported type <class 'dict'> in
    # write()". Every row must carry every dynamic column, even as None.
    rows = [
        {"employee_no": "1", "work_date": datetime.date(2026, 8, 1), "hours": 8, "status": "Present"},
        # employee "2" has NO row at all for 2026-08-02.
        {"employee_no": "2", "work_date": datetime.date(2026, 8, 1), "hours": 8, "status": "Present"},
        {"employee_no": "1", "work_date": datetime.date(2026, 8, 2), "hours": 8, "status": "Present"},
    ]
    new_rows, columns = _apply_pivot(rows, ["employee_no", "work_date", "hours", "status"], _PIVOT)
    assert columns == ["employee_no", "01 Aug", "02 Aug"]
    emp2 = next(r for r in new_rows if r["employee_no"] == "2")
    assert "02 Aug" in emp2   # the key exists...
    assert emp2["02 Aug"] is None   # ...holding None, not missing entirely
    assert isinstance(emp2["_cell_status"], dict)   # never leaks as a cell value


def test_pivot_columns_sort_chronologically_not_alphabetically():
    # "10 Aug" must sort AFTER "02 Aug" — alphabetical sort would put it first.
    rows = [
        {"employee_no": "1", "work_date": datetime.date(2026, 8, 2), "hours": 8, "status": "Present"},
        {"employee_no": "1", "work_date": datetime.date(2026, 8, 10), "hours": 8, "status": "Present"},
    ]
    _, columns = _apply_pivot(rows, ["employee_no", "work_date", "hours", "status"], _PIVOT)
    assert columns == ["employee_no", "02 Aug", "10 Aug"]


def test_pivot_carries_per_cell_status_without_it_becoming_a_column():
    rows, columns = _apply_pivot(_LONG_ROWS, _LONG_COLUMNS, _PIVOT)
    assert "_cell_status" not in columns
    peter = next(r for r in rows if r["employee_no"] == "284")
    assert peter["_cell_status"] == {"01 Aug": "Present", "02 Aug": "Half Day"}


def test_pivot_is_a_no_op_without_a_pivot_config():
    rows, columns = _apply_pivot(_LONG_ROWS, _LONG_COLUMNS, None)
    assert rows is _LONG_ROWS
    assert columns is _LONG_COLUMNS


def test_pivot_generic_over_any_dimension_not_hardcoded_to_dates():
    # column_field need not be a date at all — e.g. pivot by shift name.
    rows = [
        {"employee_no": "1", "shift": "Morning", "count": 3},
        {"employee_no": "1", "shift": "Evening", "count": 5},
    ]
    pivot = {"column_field": "shift", "value_field": "count"}
    new_rows, columns = _apply_pivot(rows, ["employee_no", "shift", "count"], pivot)
    assert columns == ["employee_no", "Evening", "Morning"]
    assert new_rows[0]["Morning"] == 3
    assert new_rows[0]["Evening"] == 5


def _load_sheet(data: bytes):
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    return wb.active


def test_excel_export_with_a_gapped_employee_does_not_crash():
    # End-to-end reproduction of the real production crash: without the
    # backfill, employee "2"'s missing "02 Aug" key made the Excel renderer's
    # cell lookup fall back to a wrong position and try to write the
    # `_cell_status` dict as a cell value.
    rows = [
        {"employee_no": "1", "work_date": datetime.date(2026, 8, 1), "hours": 8, "status": "Present"},
        {"employee_no": "2", "work_date": datetime.date(2026, 8, 1), "hours": 8, "status": "Present"},
        {"employee_no": "1", "work_date": datetime.date(2026, 8, 2), "hours": 8, "status": "Present"},
    ]
    new_rows, columns = _apply_pivot(rows, ["employee_no", "work_date", "hours", "status"], _PIVOT)
    result = QueryResult(columns=columns, rows=new_rows, sql="", row_count=len(new_rows), truncated=False)
    pivot = PivotSpec.model_validate(_PIVOT)
    presentation = PresentationSpec(
        title="Working Hours",
        columns=[ColumnPresentation(ref=c, label=c) for c in columns],
        pivot=pivot,
    )
    data = render_excel(result, presentation)   # must not raise
    ws = _load_sheet(data)
    emp2_row = next(r for r in ws.iter_rows(values_only=True) if r[0] == "2")
    assert emp2_row[columns.index("02 Aug")] is None


def test_excel_export_colors_a_pivoted_cell_by_its_status():
    rows, columns = _apply_pivot(_LONG_ROWS, _LONG_COLUMNS, _PIVOT)
    result = QueryResult(columns=columns, rows=rows, sql="", row_count=len(rows), truncated=False)
    pivot = PivotSpec.model_validate({**_PIVOT, "status_colors": {"Absent": "#F3C6C6", "Half Day": "#D9E6C3"}})
    presentation = PresentationSpec(
        title="Working Hours",
        columns=[ColumnPresentation(ref=c, label=c) for c in columns],
        pivot=pivot,
    )
    data = render_excel(result, presentation)
    ws = _load_sheet(data)

    jonathan_row = next(
        r for r in ws.iter_rows() if any(c.value == "Jonathan Peezer" for c in r)
    )
    absent_cell = next(c for c in jonathan_row if c.value == 0)
    assert absent_cell.fill.fgColor.rgb.upper().endswith("F3C6C6")

    present_cell = next(c for c in jonathan_row if c.value == 8)
    assert present_cell.fill.fgColor.rgb is None or not present_cell.fill.fgColor.rgb.upper().endswith("F3C6C6")


def test_excel_export_uncolored_status_falls_back_to_plain_format():
    # A status with no entry in status_colors must never crash — plain cell.
    rows, columns = _apply_pivot(_LONG_ROWS, _LONG_COLUMNS, _PIVOT)
    result = QueryResult(columns=columns, rows=rows, sql="", row_count=len(rows), truncated=False)
    pivot = PivotSpec.model_validate({**_PIVOT, "status_colors": {}})
    presentation = PresentationSpec(
        title="Working Hours",
        columns=[ColumnPresentation(ref=c, label=c) for c in columns],
        pivot=pivot,
    )
    render_excel(result, presentation)   # must not raise
