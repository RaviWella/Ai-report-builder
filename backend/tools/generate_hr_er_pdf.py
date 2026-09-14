"""Generate HR datamart ER PDF and HTML from docs/datamart-er.yml.

Regenerate after any structural mart change:
  python backend/tools/generate_hr_er_pdf.py

Validate metadata vs dbt (no PDF write):
  python backend/tools/generate_hr_er_pdf.py --check
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF

from datamart_er_catalog import (
    META_PATH,
    build_control_plane,
    build_control_plane_semantic,
    build_semantic_views,
    entity_tuples,
    load_meta,
    rel_tuples,
    validate,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = REPO_ROOT / "docs" / "HR_DATAMART_ER.pdf"
HTML_PATH = REPO_ROOT / "docs" / "hr-datamart-er.html"


class ErPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Mint HRM - HR Datamart ER - Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 20, 20)
        self.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def body_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def data_table(self, headers: tuple[str, ...], rows: list[tuple[str, ...]], col_widths: tuple[float, ...]) -> None:
        self.set_font("Helvetica", "", 7)
        with self.table(
            width=self.epw,
            col_widths=col_widths,
            headings_style=self._head_style(),
            line_height=4.5,
            text_align=("LEFT", "CENTER", "LEFT", "LEFT")[: len(headers)],
        ) as table:
            hdr = table.row()
            for h in headers:
                hdr.cell(h)
            for row in rows:
                r = table.row()
                for cell in row:
                    r.cell(cell)
        self.ln(4)

    @staticmethod
    def _head_style():
        from fpdf.fonts import FontFace

        return FontFace(emphasis="BOLD", fill_color=(243, 243, 243), color=(30, 30, 30))


def _kind_class(kind: str) -> str:
    k = kind.upper()
    if k == "DIM":
        return "kind-dim"
    if k == "FACT":
        return "kind-fact"
    if k == "MART":
        return "kind-mart"
    return "kind-view"


def _html_table(headers: tuple[str, ...], rows: list[tuple[str, ...]], *, kind_col: int | None = None) -> str:
    """Render an HTML table; kind_col indexes the Kind column for CSS classes."""
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_rows: list[str] = []
    for row in rows:
        cells: list[str] = []
        for i, cell in enumerate(row):
            text = html.escape(str(cell))
            if kind_col is not None and i == kind_col:
                cells.append(f'<td class="{_kind_class(str(cell))}">{text}</td>')
            elif i == 0 and headers[0].lower() in ("object", "from", "view"):
                cells.append(f'<td class="mono">{text}</td>')
            else:
                cells.append(f"<td>{text}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<table>\n"
        f"<thead><tr>{head}</tr></thead>\n"
        f"<tbody>\n{''.join(body_rows)}\n</tbody>\n"
        "</table>"
    )


def _html_section(title: str, table_html: str, *, subtitle: str = "") -> str:
    sub = f"<h3>{html.escape(subtitle)}</h3>\n" if subtitle else ""
    return (
        f'<div class="section">\n'
        f"<h2>{html.escape(title)}</h2>\n"
        f"{sub}"
        f"{table_html}\n"
        "</div>\n"
    )


def write_html() -> None:
    meta = load_meta()
    enterprise = entity_tuples("enterprise")
    leave = entity_tuples("leave")
    payroll = entity_tuples("payroll")
    semantic = build_semantic_views(meta)
    control = build_control_plane(meta)
    control_semantic = build_control_plane_semantic(meta)
    generated = date.today().isoformat()

    sections = [
        _html_section(
            "1. Enterprise HR — Entities (schema: hr)",
            _html_table(("Object", "Kind", "Primary key", "Grain / role"), enterprise, kind_col=1),
        ),
        _html_section(
            "Enterprise HR — Relationships (FK-style joins)",
            _html_table(("From (fact / mart)", "To (dimension / upstream)", "Join key / role"), rel_tuples("enterprise")),
        ),
        _html_section(
            "2. Leave Intelligence Mart — Entities (schema: hr)",
            _html_table(("Object", "Kind", "Primary key", "Grain / role"), leave, kind_col=1),
            subtitle="Phases 0–4 implemented. Conformed dim_employee and dim_date shared with Enterprise HR.",
        ),
        _html_section(
            "Leave Intelligence — Relationships",
            _html_table(("From (fact / mart)", "To (dimension / upstream)", "Join key / role"), rel_tuples("leave")),
        ),
        _html_section(
            "3. Payroll Phase 6 — Entities (schema: hr)",
            _html_table(("Object", "Kind", "Primary key", "Grain / role"), payroll, kind_col=1),
        ),
        _html_section(
            "Payroll Phase 6 — Relationships",
            _html_table(("From", "To", "Join key / role"), rel_tuples("payroll")),
        ),
        _html_section(
            "4. Semantic layer (schema: hr_semantic)",
            _html_table(("View", "Upstream marts / facts"), semantic),
            subtitle="Consumer-facing dbt views. Physical marts may change; views provide a stable API contract.",
        ),
        _html_section(
            "5. Control plane — Data dictionary (schema: hr_control)",
            _html_table(("Object", "Kind", "Primary key", "Grain / role"), control, kind_col=1),
            subtitle="ETL-maintained metadata (not dbt). Refreshed after each successful dbt run.",
        ),
    ]
    if control_semantic:
        sections.append(
            _html_section(
                "Data dictionary — Semantic exposure",
                _html_table(("View", "Reads"), control_semantic),
            )
        )

    doc = f"""<!DOCTYPE html>
<!-- AUTO-GENERATED from docs/datamart-er.yml — do not edit by hand.
     Regenerate: python backend/tools/generate_hr_er_pdf.py -->
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>HR Datamart ER</title>
  <style>
    @page {{
      size: A4 landscape;
      margin: 14mm 16mm;
      @bottom-center {{
        content: "Mint HRM · HR Datamart ER · Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        color: #666;
      }}
    }}
    @page :first {{ @bottom-center {{ content: none; }} }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      font-size: 9.5pt;
      line-height: 1.35;
      color: #141414;
      margin: 0;
    }}
    h1 {{ font-size: 22pt; font-weight: 600; margin: 0 0 6pt; }}
    h2 {{
      font-size: 13pt;
      font-weight: 600;
      margin: 18pt 0 8pt;
      padding-bottom: 4pt;
      border-bottom: 1px solid #ccc;
      page-break-after: avoid;
    }}
    h3 {{ font-size: 10.5pt; margin: 12pt 0 6pt; page-break-after: avoid; }}
    p.meta {{ color: #444; margin: 0 0 14pt; max-width: 95%; }}
    .cover {{ page-break-after: always; padding-top: 8mm; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8pt; margin: 12pt 0; }}
    .badge {{
      display: inline-block;
      padding: 2pt 8pt;
      border-radius: 4pt;
      font-size: 8pt;
      font-weight: 600;
      border: 1px solid;
    }}
    .dim {{ background: #e8f2fc; border-color: #3685bf; color: #1a4d73; }}
    .fact {{ background: #e6f4ee; border-color: #1f8a65; color: #0d5a3f; }}
    .mart {{ background: #fef3e6; border-color: #e09030; color: #8a5010; }}
    .view {{ background: #f0f0f0; border-color: #888; color: #444; }}
    .flow {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6pt;
      margin: 14pt 0;
      flex-wrap: wrap;
    }}
    .flow-box {{
      padding: 8pt 12pt;
      border: 1px solid #3685bf;
      border-radius: 6pt;
      text-align: center;
      min-width: 90pt;
      background: #f8fbff;
    }}
    .flow-arrow {{ font-size: 14pt; color: #888; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 8pt;
      margin-bottom: 10pt;
    }}
    th, td {{
      border: 1px solid #ccc;
      padding: 4pt 6pt;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f3f3f3; font-weight: 600; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
    .kind-dim {{ color: #3685bf; font-weight: 600; }}
    .kind-fact {{ color: #1f8a65; font-weight: 600; }}
    .kind-mart {{ color: #c07010; font-weight: 600; }}
    .kind-view {{ color: #666; font-weight: 600; }}
    .section {{ page-break-before: always; }}
    .section:first-of-type {{ page-break-before: auto; }}
    .mono {{ font-family: Consolas, "Courier New", monospace; font-size: 7.5pt; }}
    .note {{ font-size: 8pt; color: #555; margin-top: 8pt; }}
  </style>
</head>
<body>

  <div class="cover">
    <h1>HR Datamart Entity-Relationship Overview</h1>
    <p class="meta">
      <strong>Generated:</strong> {html.escape(generated)} &nbsp;·&nbsp;
      <strong>Warehouse:</strong> PostgreSQL per tenant (<code>hrm_wh_{{tenant_id}}</code>) &nbsp;·&nbsp;
      <strong>Pattern:</strong> Medallion + Kimball star schema (conformed dimensions, surrogate keys)
    </p>
    <div class="legend">
      <span class="badge dim">DIM — Dimension</span>
      <span class="badge fact">FACT — Atomic grain</span>
      <span class="badge mart">MART — BI-ready aggregate</span>
      <span class="badge view">VIEW — Semantic / legacy</span>
    </div>
    <h2>Medallion data flow</h2>
    <div class="flow">
      <div class="flow-box"><strong>Bronze</strong><br><code>hr_raw</code><br>ETL staging</div>
      <span class="flow-arrow">→</span>
      <div class="flow-box"><strong>Silver / Gold</strong><br><code>hr</code><br>Facts &amp; marts</div>
      <span class="flow-arrow">→</span>
      <div class="flow-box"><strong>Semantic</strong><br><code>hr_semantic</code><br>Consumer views</div>
    </div>
    <p class="note">
      <strong>Control plane:</strong> <code>hr_control</code> — ETL run log, watermarks, source registry,
      <code>data_dictionary_*</code> (auto-synced after dbt).
    </p>
    <p class="note">
      Source: <span class="mono">docs/datamart-er.yml</span> ·
      <span class="mono">backend/dbt_project/hr_mart/models/marts/</span>
    </p>
  </div>

{"".join(sections)}
</body>
</html>
"""
    HTML_PATH.write_text(doc, encoding="utf-8")


def write_pdf() -> None:
    meta = load_meta()
    enterprise = entity_tuples("enterprise")
    leave = entity_tuples("leave")
    payroll = entity_tuples("payroll")
    semantic = build_semantic_views(meta)
    control = build_control_plane(meta)
    control_semantic = build_control_plane_semantic(meta)

    pdf = ErPdf(orientation="L", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 14, "HR Datamart Entity-Relationship Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.body_text(
        "Warehouse: PostgreSQL per tenant (hrm_wh_{tenant_id})\n"
        "Architecture: Medallion (hr_raw -> hr -> hr_semantic) + Kimball star schema\n"
        f"Metadata: {META_PATH.relative_to(REPO_ROOT)}\n"
        "Domains: Enterprise HR, Leave Intelligence (Phases 0-4), Payroll Phase 6"
    )

    pdf.section_title("Legend")
    pdf.set_font("Helvetica", "", 9)
    for label in (
        "DIM  - Dimension (conformed, surrogate keys)",
        "FACT - Atomic grain fact table",
        "MART - BI-ready aggregate / denormalized report table",
        "VIEW - Semantic or legacy compatibility layer",
    ):
        pdf.cell(0, 5, label, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.section_title("Medallion data flow")
    pdf.body_text(
        "Bronze (hr_raw): ETL staging from MintHRM source (stg_*)\n"
        "Silver/Gold (hr): dbt dimensions, facts, and marts (*_sk surrogate keys)\n"
        "Semantic (hr_semantic): Stable vw_* views for APIs and reports\n"
        "Control (hr_control): ETL log, watermarks, data_dictionary_* (auto-sync after dbt)\n\n"
        "Conformed dim_employee and dim_date are shared across Enterprise, Leave, and Payroll."
    )

    pdf.add_page()
    pdf.section_title("1. Enterprise HR - Entities (schema: hr)")
    pdf.data_table(("Object", "Kind", "Primary key", "Grain / role"), enterprise, (62, 14, 38, 66))
    pdf.section_title("Enterprise HR - Relationships")
    pdf.data_table(
        ("From (fact/mart)", "To (dim/upstream)", "Join key"),
        rel_tuples("enterprise"),
        (75, 75, 40),
    )

    pdf.add_page()
    pdf.section_title("2. Leave Intelligence Mart - Entities (schema: hr)")
    pdf.body_text("Phases 0-4 implemented. Legacy fact_leave_balance bridges to fct_leave_application.")
    pdf.data_table(("Object", "Kind", "Primary key", "Grain / role"), leave, (62, 14, 38, 66))
    pdf.section_title("Leave Intelligence - Relationships")
    pdf.data_table(
        ("From (fact/mart)", "To (dim/upstream)", "Join key"),
        rel_tuples("leave"),
        (75, 75, 40),
    )

    pdf.add_page()
    pdf.section_title("3. Payroll Phase 6 - Entities (schema: hr)")
    pdf.data_table(("Object", "Kind", "Primary key", "Grain / role"), payroll, (62, 14, 38, 66))
    pdf.section_title("Payroll Phase 6 - Relationships")
    pdf.data_table(("From", "To", "Join key / role"), rel_tuples("payroll"), (75, 75, 40))

    pdf.add_page()
    pdf.section_title("4. Semantic layer (schema: hr_semantic)")
    pdf.body_text("Consumer-facing dbt views. Physical marts may change; views provide a stable API contract.")
    pdf.data_table(("View", "Upstream marts / facts"), semantic, (55, 125))

    if control:
        pdf.add_page()
        pdf.section_title("5. Control plane - Data dictionary (schema: hr_control)")
        pdf.body_text("ETL-maintained metadata tables. Refreshed after each successful dbt run (SYNC_DATA_DICTIONARY_ON_ETL).")
        pdf.data_table(("Object", "Kind", "Primary key", "Grain / role"), control, (62, 14, 38, 66))
        if control_semantic:
            pdf.section_title("Data dictionary - Semantic exposure")
            pdf.data_table(("View", "Reads"), control_semantic, (55, 125))

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(PDF_PATH))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate HR datamart ER docs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate docs/datamart-er.yml against dbt models (exit 1 on drift)",
    )
    args = parser.parse_args()

    errors = validate()
    if errors:
        print("Datamart ER documentation is out of date:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            f"\nUpdate {META_PATH.relative_to(REPO_ROOT)} then run without --check to regenerate.",
            file=sys.stderr,
        )
        return 1

    if args.check:
        print("OK: datamart-er.yml matches dbt marts and semantic views.")
        return 0

    write_pdf()
    write_html()
    print(f"Wrote {PDF_PATH}")
    print(f"Wrote {HTML_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
