"""One-off helper: ensure stg_prl_overtime exists, extract, and build OT worksheet view."""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.core.warehouse import get_layout_sync, get_warehouse_engine_sync
from app.services.hr_etl.dbt_runner import HrDbtRunner, _extract_dbt_failure_message
from app.services.hr_etl.staging_ddl import STAGING_DDL
from app.services.hr_etl.staging_schema import ensure_staging_tables


def main(tenant_id: str = "demo_tenant") -> int:
    pg = get_warehouse_engine_sync(tenant_id)
    layout = get_layout_sync(tenant_id)
    schema = layout.raw_schema

    with pg.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        for ddl in STAGING_DDL:
            if "stg_prl_overtime" in ddl:
                conn.execute(text(ddl.format(schema=schema)))
                print(f"Ensured {schema}.stg_prl_overtime")

    ensure_staging_tables(pg, tenant_id)

    try:
        from app.services.hr_etl.source_connection import get_source_engine

        src, _ = get_source_engine(tenant_id)
        from app.services.hr_etl.extractors_minthrm import extract_prl_overtime

        rows = extract_prl_overtime(src, pg, tenant_id, incremental=False)
        print(f"Extracted {rows} rows into {schema}.stg_prl_overtime")
    except Exception as exc:
        print(f"Extract skipped ({type(exc).__name__}): {exc}")

    runner = HrDbtRunner(tenant_id)
    summary = runner._run_dbt(
        ["run", "--select", "stg_processed_prl_overtime", "vw_employee_ot_worksheet"]
    )
    if not summary.get("success"):
        print("dbt failed:", _extract_dbt_failure_message(summary))
        return 1

    with pg.connect() as conn:
        n = conn.execute(
            text(f'SELECT COUNT(*) FROM custom_reports.vw_employee_ot_worksheet')
        ).scalar()
        print(f"custom_reports.vw_employee_ot_worksheet rows: {n}")
    return 0


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "demo_tenant"
    raise SystemExit(main(tid))
