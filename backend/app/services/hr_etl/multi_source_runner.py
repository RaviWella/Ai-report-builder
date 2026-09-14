"""Orchestrate ETL across multiple sources (legacy MySQL + new Postgres schemas)."""
from __future__ import annotations

import logging
import traceback
from contextlib import nullcontext
from typing import Any

from sqlalchemy.engine import Engine

from app.core.warehouse import (
    ensure_warehouse_ready_sync,
    get_platform_engine_sync,
    get_warehouse_engine_sync,
)
from app.services.hr_etl import control
from app.services.hr_etl.errors import format_run_error
from app.services.hr_etl.dbt_runner import HrDbtRunner, require_dbt_success
from app.services.hr_etl.extractors import reset_staging_suffix, set_staging_suffix
from app.services.hr_etl.registry import get_extractors
from app.services.hr_etl.source_connection import source_dialect
from app.services.hr_etl.source_mapping import source_mapping
from app.services.hr_etl.validation import HrValidationRunner
from app.services.tenant_etl_sources import (
    TenantEtlSourceRow,
    build_engine_for_source,
    load_sources_for_etl,
)

logger = logging.getLogger("hr_etl.multi_source")


def _extract_one_source(
    warehouse_pg: Engine,
    tenant_id: str,
    run_id: int,
    source_row: TenantEtlSourceRow,
    *,
    incremental: bool,
) -> tuple[dict[str, int], int]:
    source_engine, _config = build_engine_for_source(
        warehouse_pg, tenant_id, source_row
    )
    totals: dict[str, int] = {}
    total_rows = 0
    suffix_token = set_staging_suffix(source_row.staging_suffix)
    profile = source_row.extractor_profile
    variant = source_row.mapping_variant_resolved()

    try:
        extractor_list, incremental_tables = get_extractors(profile)
        use_mapping = profile == "minthrm"
        mapping_ctx = (
            source_mapping(
                tenant_id,
                variant,
                profile=profile,
                source_schema=source_row.source_schema,
            )
            if use_mapping
            else nullcontext()
        )
        prefix = f"[{source_row.source_key}] "
        with source_dialect(variant), mapping_ctx:
            for step_name, fn in extractor_list:
                staged_name = (
                    step_name
                    if not source_row.staging_suffix
                    else f"{step_name}__{source_row.staging_suffix}"
                )
                step_id = control.start_step(
                    warehouse_pg,
                    tenant_id,
                    run_id,
                    f"{source_row.source_key}/{step_name}",
                    "extract",
                )
                try:
                    use_incr = incremental and step_name in incremental_tables
                    if use_incr:
                        rows = fn(
                            source_engine, warehouse_pg, tenant_id, incremental=True
                        )
                    else:
                        rows = fn(source_engine, warehouse_pg, tenant_id)
                    totals[staged_name] = rows
                    total_rows += rows
                    control.complete_step(
                        warehouse_pg, tenant_id, step_id, rows_processed=rows
                    )
                    logger.info(
                        "%sextract %s: %d rows (suffix=%s schema=%s)",
                        prefix,
                        step_name,
                        rows,
                        source_row.staging_suffix or "primary",
                        source_row.source_schema or "-",
                    )
                except Exception as step_err:
                    tb = traceback.format_exc(limit=5)
                    logger.error("%sstep %s failed: %s", prefix, step_name, step_err)
                    control.fail_step(
                        warehouse_pg, tenant_id, step_id, f"{step_err}\n{tb}"
                    )
                    raise
    finally:
        reset_staging_suffix(suffix_token)
        source_engine.dispose()

    return totals, total_rows


def run_tenant_etl(
    tenant_id: str,
    run_type: str,
    triggered_by: str,
    *,
    incremental: bool = False,
    run_id: int | None = None,
    platform_pg: Engine | None = None,
    warehouse_pg: Engine | None = None,
) -> dict[str, Any]:
    """Full tenant ETL: extract → dbt → validate (platform + warehouse connections)."""
    platform = platform_pg or get_platform_engine_sync()
    warehouse = warehouse_pg or get_warehouse_engine_sync(tenant_id)
    ensure_warehouse_ready_sync(warehouse, tenant_id)

    sources = load_sources_for_etl(platform, tenant_id)
    if not sources:
        raise LookupError(
            f"No ETL sources configured for tenant '{tenant_id}'. "
            "Add sources via /tenants/etl-sources or register tenant_registry."
        )

    if run_id is None:
        run_id = control.start_run(warehouse, tenant_id, run_type, triggered_by)
    totals: dict[str, int] = {}
    total_rows = 0
    failed = False
    error_message: str | None = None
    validation_summary: dict[str, Any] = {}
    dbt_summary: dict[str, Any] = {}
    sources_summary: list[dict[str, Any]] = []

    try:
        logger.info(
            "Multi-source ETL run %d tenant=%s sources=%s",
            run_id,
            tenant_id,
            [s.source_key for s in sources],
        )
        for src in sources:
            src_totals, src_rows = _extract_one_source(
                warehouse, tenant_id, run_id, src, incremental=incremental
            )
            totals.update(src_totals)
            total_rows += src_rows
            sources_summary.append(
                {
                    "source_key": src.source_key,
                    "display_name": src.display_name,
                    "source_type": src.source_type,
                    "source_schema": src.source_schema,
                    "staging_suffix": src.staging_suffix or "(primary)",
                    "rows": src_rows,
                }
            )

        try:
            dbt_step_id = control.start_step(
                warehouse, tenant_id, run_id, "dbt_run", "transform"
            )
            dbt = HrDbtRunner(tenant_id=tenant_id)
            dbt_summary = dbt.run()
            require_dbt_success(dbt_summary)
            control.complete_step(
                warehouse,
                tenant_id,
                dbt_step_id,
                rows_processed=dbt_summary.get("total", 0),
                details=dbt_summary,
            )

            from app.services.hr_etl.data_dictionary_sync import maybe_sync_after_etl

            dd_summary = maybe_sync_after_etl(
                tenant_id, dbt_succeeded=True, warehouse_engine=warehouse
            )
            totals["data_dictionary"] = dd_summary
        except Exception as dbt_err:
            logger.error("dbt failed: %s", dbt_err)
            raise

        try:
            val_step_id = control.start_step(
                warehouse, tenant_id, run_id, "validate", "validate"
            )
            validation_summary = HrValidationRunner(warehouse, tenant_id).run_all(
                run_id=run_id
            )
            control.complete_step(
                warehouse,
                tenant_id,
                val_step_id,
                rows_processed=validation_summary.get("failed", 0),
                details=validation_summary,
            )
        except Exception as val_err:
            logger.error("validation failed: %s", val_err)

        control.complete_run(
            warehouse,
            tenant_id,
            run_id,
            rows_extracted=total_rows,
            rows_loaded=total_rows,
            details={
                "per_table": totals,
                "sources": sources_summary,
                "dbt": dbt_summary,
                "validation": validation_summary,
            },
        )
    except Exception as exc:
        failed = True
        error_message = format_run_error(exc, include_traceback=True)
        control.fail_run(
            warehouse,
            tenant_id,
            run_id,
            error_message,
            details={"per_table": totals, "sources": sources_summary},
            exc=exc,
        )

    return {
        "run_id": run_id,
        "tenant_id": tenant_id,
        "status": "failed" if failed else "completed",
        "rows_loaded": total_rows,
        "per_table": totals,
        "sources": sources_summary,
        "validation": validation_summary if not failed else {},
        "error": error_message,
    }
