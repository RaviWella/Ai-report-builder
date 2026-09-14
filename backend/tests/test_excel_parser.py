"""Excel / CSV / HTML-.xls sample upload parsing."""

from app.ingestion.document_parser import parse_document
from app.ingestion.excel_parser import parse_csv_headers, parse_excel_headers


_HTML_XLS = b"""<!DOCTYPE html><html><body><table>
<tr><td>Employee No</td><td>Name</td><td>Department</td></tr>
<tr><td>1</td><td>John</td><td>HR</td></tr>
</table></body></html>"""


def test_html_disguised_as_xls():
    parsed = parse_document(
        _HTML_XLS,
        filename="Employee Information Report.xls",
        content_type="application/vnd.ms-excel",
    )
    assert [c.header for c in parsed.columns] == ["Employee No", "Name", "Department"]


def test_csv_headers():
    raw = b"Emp No,Name\n1,Alice\n"
    parsed = parse_csv_headers(raw)
    assert [c.header for c in parsed.columns] == ["Emp No", "Name"]


def test_csv_with_title_row():
    """HR exports often put a report title on line 1, headers on line 2."""
    cols = [f"Col{i}" for i in range(1, 25)]
    raw = (
        "Employee Information Report\n"
        + ",".join(cols)
        + "\n"
        + ",".join(str(i) for i in range(24))
        + "\n"
    ).encode()
    parsed = parse_csv_headers(raw)
    assert [c.header for c in parsed.columns] == cols


def test_csv_semicolon_delimiter():
    raw = b"Emp No;Name\n1;Alice\n"
    parsed = parse_csv_headers(raw)
    assert [c.header for c in parsed.columns] == ["Emp No", "Name"]


def test_xlsx_headers():
    import io

    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame([["Dept", "Headcount"], ["HR", 10]]).to_excel(buf, index=False, header=False)
    parsed = parse_excel_headers(buf.getvalue(), filename="sample.xlsx")
    assert [c.header for c in parsed.columns] == ["Dept", "Headcount"]
