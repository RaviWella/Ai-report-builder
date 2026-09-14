#!/usr/bin/env python3
"""Inspect a single ETL run — database, schemas, steps, row counts."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

from app.core.application_db import build_url
from app.core.warehouse import connection_params, get_layout_sync


def main() -> None:
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else "demo_tenant"
    run_id = int(sys.argv[2]) if len(sys.argv) > 2 else 21

    params = connection_params(tenant_id)
    layout = get_layout_sync(tenant_id)
    url = build_url(
        host=params["host"],
        port=int(params["port"]),
        user=params["user"],
        password=params["password"],
        database=params["database"],
        driver="psycopg2",
    )

    print("=== Where ETL writes data ===")
    print(f"Tenant:              {tenant_id}")
    print(f"Postgres database:   {params['database']}")
    print(f"Host:                {params['host']}:{params['port']}")
    print(f"Control (run log):   {layout.control_schema}.hr_etl_run_log")
    print(f"Staging (extract):   {layout.raw_schema}.stg_*")
    print(f"Marts (dbt):         {layout.mart_schema}.*")
    print(f"Semantic views:      {layout.semantic_schema}.vw_*")
    print()
    print("Platform DB (read-only for ETL): hrm_platform / hrm_control.tenant_registry, tenant_etl_sources")
    print()

    wh = create_engine(url)
    with wh.connect() as c:
        run = c.execute(
            text(
                f"""
                SELECT run_id, run_type, status, started_at, completed_at,
                       rows_extracted, rows_loaded, rows_transformed, triggered_by,
                       error_message, details
                FROM "{layout.control_schema}".hr_etl_run_log
                WHERE run_id = :rid
                """
            ),
            {"rid": run_id},
        ).mappings().first()
        if not run:
            print(f"Run #{run_id} not found in {params['database']}.{layout.control_schema}.hr_etl_run_log")
            return
        print(f"=== Run #{run_id} ===")
        for k, v in dict(run).items():
            if k != "details":
                print(f"  {k}: {v}")
        details = run.get("details")
        if details:
            if isinstance(details, str):
                details = json.loads(details)
            per_table = details.get("per_table") or {}
            if per_table:
                print("\n  Staging tables updated (schema {}.*):".format(layout.raw_schema))
                for name, n in sorted(per_table.items(), key=lambda x: -x[1])[:25]:
                    print(f"    {layout.raw_schema}.{name}: {n} rows")
            sources = details.get("sources")
            if sources:
                print("\n  Source systems read (MySQL/Postgres upstream — not written by ETL):")
                for s in sources:
                    print(f"    - {s.get('display_name')} ({s.get('source_key')})")

        steps = c.execute(
            text(
                f"""
                SELECT step_id, step_name, step_type, status, rows_processed,
                       error_message
                FROM "{layout.control_schema}".hr_etl_step_log
                WHERE run_id = :rid
                ORDER BY step_id
                """
            ),
            {"rid": run_id},
        ).fetchall()
        print(f"\n=== Steps (run #{run_id}) ===")
        for s in steps:
            print(f"  {s}")


if __name__ == "__main__":
    main()
