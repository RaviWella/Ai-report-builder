"""Inspect mart_horizontal_paysheet_dynamic column population."""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.core.warehouse import get_warehouse_engine_sync


def main() -> int:
    tenant = sys.argv[1] if len(sys.argv) > 1 else "demo_tenant"
    eng = get_warehouse_engine_sync(tenant)
    with eng.connect() as c:
        cols = [
            r[0]
            for r in c.execute(
                text(
                    """
                    select column_name
                    from information_schema.columns
                    where table_schema = 'hr'
                      and table_name = 'mart_horizontal_paysheet_dynamic'
                      and (
                        column_name like '%__%'
                        or column_name like '%addition%'
                        or column_name like '%deduction%'
                      )
                      and column_name not in (
                        'total_allowance', 'total_deduction', 'pay_cut_amount'
                      )
                    order by 1
                    """
                )
            )
        ]
        print(f"Dynamic-style columns ({len(cols)}):", cols[:12], "..." if len(cols) > 12 else "")
        rows = c.execute(
            text(
                """
                select pivot_key, pivot_label, line_count,
                       round(total_amount::numeric, 2) as total_amount
                from hr.mart_payroll_pivot_column_catalog
                order by line_count desc
                limit 20
                """
            )
        ).fetchall()
        print("\nTop pivot catalog entries:")
        for r in rows:
            print(f"  {r.pivot_key}: {r.pivot_label} ({r.line_count} lines, total={r.total_amount})")
        if cols:
            col = cols[0]
            stat = c.execute(
                text(
                    f"""
                    select count(*) as n_rows,
                           count(*) filter (where coalesce("{col}", 0) <> 0) as n_nonzero
                    from hr.mart_horizontal_paysheet_dynamic
                    """
                )
            ).one()
            print(f"\nSample column {col!r}: {stat.n_nonzero}/{stat.n_rows} rows non-zero")
    eng.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
