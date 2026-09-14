"""Refresh leave staging + build Phase 1 leave marts."""
from __future__ import annotations

import inspect
import sys

from app.core.warehouse import get_warehouse_engine_sync
from app.services.hr_etl.dbt_runner import HrDbtRunner, require_dbt_success
from app.services.hr_etl.registry import get_extractors
from app.services.hr_etl.source_connection import normalize_source_type, source_dialect
from app.services.hr_etl.staging_schema import ensure_staging_tables
from app.services.source_databases import build_source_engine, resolve_config_sync

LEAVE_TABLES = (
    "stg_leave_types",
    "stg_leave_requests",
    "stg_leave_application_dates",
)


def main() -> int:
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else "demo_tenant"
    pg = get_warehouse_engine_sync(tenant_id)
    src_cfg = resolve_config_sync(tenant_id)
    source = build_source_engine(src_cfg)
    dialect = normalize_source_type(src_cfg.source_type)

    ensure_staging_tables(pg, tenant_id, force=True)

    extractors, _incremental = get_extractors()
    by_name = dict(extractors)

    with source_dialect(dialect):
        for table in LEAVE_TABLES:
            fn = by_name.get(table)
            if fn is None:
                raise RuntimeError(f"No extractor registered for {table}")
            sig = inspect.signature(fn)
            kwargs = {}
            if "incremental" in sig.parameters:
                kwargs["incremental"] = False
            count = fn(source, pg, tenant_id, **kwargs)
            print(f"extract {table}: {count} rows")

    runner = HrDbtRunner(tenant_id)
    runner.ensure_deps()

    staging = runner._run_dbt(
        [
            "run",
            "--select",
            "int_leave_type int_leave_application int_leave_daily",
        ]
    )
    require_dbt_success(staging)

    snap = runner._run_dbt(["snapshot", "--select", "snap_leave_type"])
    require_dbt_success(snap)

    build = runner._run_dbt(
        [
            "build",
            "--select",
            "int_leave_type int_leave_application int_leave_daily "
            "dim_leave_type dim_leave_status dim_leave_source "
            "fct_leave_application fct_leave_daily fact_leave_balance vw_leave_summary",
            "--exclude",
            "resource_type:test",
        ]
    )
    require_dbt_success(build)
    print("OK leave Phase 1 build for", tenant_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
