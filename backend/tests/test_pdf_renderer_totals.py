"""Regression test: the PDF export's grand-total column sum used the same
positional row-key bug already fixed for cell values elsewhere in this file
and in excel_renderer.py (see app/rendering/row_key.py) — `_column_sum`
matched a row's value to a column by bare positional index into the row
dict's own key order, silently summing the WRONG column whenever
presentation.columns' order diverged from the row dict's actual key order.
"""

from __future__ import annotations

from app.rendering.pdf_renderer import _column_sum


def test_column_sum_matches_by_identity_not_position():
    # Row dict key order (SQL SELECT order) differs from the presentation's
    # column order — exactly the divergence that caused the export bug.
    rows = [
        {"Department": "Finance", "Amount": 100},
        {"Department": "Finance", "Amount": 200},
    ]
    # ci=0 here is the presentation's "Amount" column, but each row's OWN
    # first key is "Department" — a positional lookup would sum strings (0).
    total = _column_sum(rows, ci=0, ref="payroll.amount", label="Amount")
    assert total == 300


def test_column_sum_skips_subtotal_rows():
    rows = [
        {"Amount": 100},
        {"Amount": 200, "_row_kind": "subtotal"},
        {"Amount": 50},
    ]
    assert _column_sum(rows, ci=0, ref="payroll.amount", label="Amount") == 150
