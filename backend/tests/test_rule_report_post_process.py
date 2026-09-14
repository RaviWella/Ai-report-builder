"""Presentation-only post-processing for rule reports: row numbering and
per-group subtotal rows. Pure functions over already-fetched rows — no DB,
no engine involvement. Generic (any rule report may opt in via
presentation_spec), so a report that doesn't set these is unaffected."""

from app.services.report_service import _apply_row_numbers, _inject_subtotals


def test_row_numbers_applied_in_place():
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    _apply_row_numbers(rows, "s_no")
    assert [r["s_no"] for r in rows] == [1, 2, 3]


def test_row_numbers_column_is_first_key_for_positional_export_alignment():
    # Excel/PDF renderers align cells to result.columns POSITIONALLY via each row
    # dict's key order, not by name lookup — s_no must lead every row exactly like
    # it leads result.columns, or every other exported cell shifts left by one.
    rows = [{"employee_no": "94011413", "count": 1}]
    _apply_row_numbers(rows, "s_no")
    assert list(rows[0].keys()) == ["s_no", "employee_no", "count"]
    assert rows[0] == {"s_no": 1, "employee_no": "94011413", "count": 1}


def test_row_numbers_noop_without_column():
    rows = [{"a": 1}, {"a": 2}]
    _apply_row_numbers(rows, None)
    assert rows == [{"a": 1}, {"a": 2}]


def test_subtotal_inserted_after_each_group():
    rows = [
        {"emp": "E1", "date": "2026-06-01", "count": 1, "amount": 352},
        {"emp": "E1", "date": "2026-06-02", "count": 2, "amount": 704},
        {"emp": "E2", "date": "2026-06-01", "count": 1, "amount": 352},
    ]
    cfg = {"group_by": ["emp"], "sum_columns": ["count", "amount"],
           "label_column": "date", "label": "Total"}
    out = _inject_subtotals(rows, cfg)
    assert [r.get("_row_kind") for r in out] == [None, None, "subtotal", None, "subtotal"]
    e1_total = out[2]
    assert e1_total["emp"] == "E1"          # descriptive columns carried from the last row
    assert e1_total["date"] == "Total"      # label overrides the group column
    assert e1_total["count"] == 3           # 1 + 2
    assert e1_total["amount"] == 1056       # 352 + 704
    e2_total = out[4]
    assert e2_total["emp"] == "E2"
    assert e2_total["count"] == 1


def test_subtotal_ignores_non_numeric_values_in_sum_columns():
    rows = [{"emp": "E1", "count": 1}, {"emp": "E1", "count": None}]
    cfg = {"group_by": ["emp"], "sum_columns": ["count"], "label_column": "emp"}
    out = _inject_subtotals(rows, cfg)
    assert out[-1]["count"] == 1   # the None is skipped, not summed as 0-breaking


def test_subtotal_noop_without_config_or_rows():
    rows = [{"emp": "E1"}]
    assert _inject_subtotals(rows, None) == rows
    assert _inject_subtotals([], {"group_by": ["emp"], "sum_columns": [], "label_column": "emp"}) == []
