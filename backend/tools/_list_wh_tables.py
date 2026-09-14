"""List warehouse tables and key columns (demo_tenant) → warehouse_schema_demo_tenant.txt"""
from __future__ import annotations

from pathlib import Path

from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.schema import introspect_table_columns, list_warehouse_tables

OUT = Path(__file__).resolve().parent / "warehouse_schema_demo_tenant.txt"


def _run() -> None:
    tables = sorted(list_warehouse_tables())
    lines: list[str] = [
        f"# Warehouse schema dump — demo_tenant",
        f"# tables={len(tables)} schemas=hr, hr_semantic, hr_snap",
        "",
    ]
    for q in tables:
        cols = list(introspect_table_columns(q) or [])
        short = q.rsplit(".", 1)[-1]
        keys = [c for c in cols if c.endswith("_sk") or c.endswith("_id") or c in ("emp_no",)]
        lines.append(f"## {q} ({len(cols)} columns)")
        if keys:
            lines.append(f"  keys: {', '.join(sorted(keys)[:25])}")
        lines.append(f"  all: {', '.join(sorted(cols)[:50])}")
        if len(cols) > 50:
            lines.append(f"  ... +{len(cols) - 50} more")
        lines.append("")
    lines.append("## Not present in this tenant")
    for missing in ("fact_leave_transaction", "dim_leave_type", "fact_payroll_detail"):
        if not any(t.endswith(missing) for t in tables):
            lines.append(f"  - {missing}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(tables)} tables)")


if __name__ == "__main__":
    run_with_datamart_context("demo_tenant", _run)
