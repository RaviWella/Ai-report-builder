"""HR ETL Runner — per-tenant orchestrator.

Mirrors finance_etl/runner.py exactly:
  1. Extract from MySQL → {tenant}_hr_raw (staging)
  2. Run dbt transforms → {tenant}_hr (dimensional mart)
  3. Run validators
  4. Log everything to {tenant}_hr_control

Usage:
    runner = HrEtlRunner(source_engine, pg_engine, tenant_id="acme_corp")
    result = runner.run_full_load()
    result = runner.run_incremental()
"""
from __future__ import annotations

import logging
import traceback
from typing import Any

from sqlalchemy.engine import Engine

from app.core.warehouse import get_warehouse_engine_sync
from app.services.hr_etl import control
from app.services.hr_etl.registry import get_extractors
from app.services.hr_etl.dbt_runner import HrDbtRunner, require_dbt_success
from app.services.hr_etl.validation import HrValidationRunner
from contextlib import nullcontext

from app.services.hr_etl.source_connection import SourceType, source_dialect
from app.services.hr_etl.source_mapping import resolve_mapping_profile, source_mapping

logger = logging.getLogger("hr_etl")


class HrEtlRunner:
    """Run the HR ETL end-to-end for a single tenant."""

    def __init__(
        self,
        source: Engine,
        pg: Engine,
        tenant_id: str,
        *,
        source_type: SourceType = "mysql",
    ):
        self.source = source
        self.source_type = source_type
        self.pg = pg
        self.tenant_id = tenant_id

    def run_full_load(self, triggered_by: str = "manual") -> dict[str, Any]:
        """Truncate + reload every staging table."""
        return self._run("full_load", triggered_by, incremental=False)

    def run_incremental(self, triggered_by: str = "manual") -> dict[str, Any]:
        """Watermark-based incremental — only rows changed since last run."""
        return self._run("incremental", triggered_by, incremental=True)

    def _run(
        self, run_type: str, triggered_by: str, *, incremental: bool
    ) -> dict[str, Any]:
        tid = self.tenant_id
        run_id = control.start_run(self.pg, tid, run_type, triggered_by)
        logger.info(
            "HR ETL run %d [%s] tenant=%s source=%s started by %s",
            run_id, run_type, tid, self.source_type, triggered_by,
        )

        totals: dict[str, int] = {}
        total_rows = 0
        failed = False
        error_message: str | None = None
        validation_summary: dict[str, Any] = {}
        dbt_summary: dict[str, Any] = {}

        try:
            extractor_list, incremental_tables = get_extractors()
            # ── 1. Extract ──────────────────────────────────────────
            mapping_ctx = (
                source_mapping(tid, self.source_type)
                if resolve_mapping_profile() == "minthrm"
                else nullcontext()
            )
            with source_dialect(self.source_type), mapping_ctx:
                for step_name, fn in extractor_list:
                    step_id = control.start_step(self.pg, tid, run_id, step_name, "extract")
                    try:
                        use_incr = incremental and step_name in incremental_tables
                        if use_incr:
                            rows = fn(self.source, self.pg, tid, incremental=True)
                        else:
                            rows = fn(self.source, self.pg, tid)
                        totals[step_name] = rows
                        total_rows += rows
                        control.complete_step(self.pg, tid, step_id, rows_processed=rows)
                    except Exception as step_err:
                        tb = traceback.format_exc(limit=5)
                        logger.error("step %s failed: %s\n%s", step_name, step_err, tb)
                        control.fail_step(self.pg, tid, step_id, f"{step_err}\n{tb}")
                        raise

            # ── 2. dbt transforms ───────────────────────────────────
            try:
                dbt_step_id = control.start_step(
                    self.pg, tid, run_id, "dbt_run", "transform"
                )
                dbt = HrDbtRunner(tenant_id=tid)
                dbt_summary = dbt.run()
                require_dbt_success(dbt_summary)
                control.complete_step(
                    self.pg, tid, dbt_step_id,
                    rows_processed=dbt_summary.get("total", 0),
                    details=dbt_summary,
                )
                totals["dbt_models_built"] = (
                    dbt_summary.get("counts", {}).get("success", 0)
                    or dbt_summary.get("total", 0)
                )

                # dbt test
                dbt_test_step_id = control.start_step(
                    self.pg, tid, run_id, "dbt_test", "validate"
                )
                test_summary = dbt.test()
                control.complete_step(
                    self.pg, tid, dbt_test_step_id,
                    rows_processed=test_summary.get("counts", {}).get("fail", 0),
                    details=test_summary,
                )

                # ── 2b. Data dictionary (auto-sync new staging + mart tables) ──
                from app.services.hr_etl.data_dictionary_sync import maybe_sync_after_etl

                dd_summary = maybe_sync_after_etl(
                    tid,
                    dbt_succeeded=True,
                    warehouse_engine=get_warehouse_engine_sync(tid),
                )
                totals["data_dictionary"] = dd_summary.get("warehouse_fields", 0)
            except Exception as dbt_err:
                logger.error("dbt step failed: %s\n%s", dbt_err, traceback.format_exc())
                for sid_name in ("dbt_step_id", "dbt_test_step_id"):
                    sid = locals().get(sid_name)
                    if sid:
                        try:
                            control.fail_step(self.pg, tid, sid, str(dbt_err))
                        except Exception:
                            pass

            # ── 3. Validate ─────────────────────────────────────────
            try:
                val_step_id = control.start_step(
                    self.pg, tid, run_id, "validate", "validate"
                )
                validation_summary = HrValidationRunner(self.pg, tid).run_all(
                    run_id=run_id
                )
                control.complete_step(
                    self.pg, tid, val_step_id,
                    rows_processed=validation_summary.get("failed", 0),
                    details={
                        "total":    validation_summary.get("total", 0),
                        "passed":   validation_summary.get("passed", 0),
                        "errors":   validation_summary.get("errors", 0),
                        "warnings": validation_summary.get("warnings", 0),
                    },
                )
            except Exception as val_err:
                logger.error("validation failed: %s", val_err)
                try:
                    control.fail_step(self.pg, tid, val_step_id, str(val_err))
                except Exception:
                    pass

            control.complete_run(
                self.pg, tid, run_id,
                rows_extracted=total_rows,
                rows_loaded=total_rows,
                details={
                    "per_table": totals,
                    "dbt": dbt_summary,
                    "validation": validation_summary,
                    "data_dictionary": totals.get("data_dictionary"),
                },
            )
            logger.info(
                "HR ETL run %d tenant=%s completed: %d rows, %d/%d checks",
                run_id, tid, total_rows,
                validation_summary.get("passed", 0),
                validation_summary.get("total", 0),
            )

        except Exception as exc:
            failed = True
            error_message = str(exc)
            control.fail_run(
                self.pg, tid, run_id, error_message,
                details={"per_table": totals},
            )

        return {
            "run_id":      run_id,
            "tenant_id":   tid,
            "status":      "failed" if failed else "completed",
            "rows_loaded": total_rows,
            "per_table":   totals,
            "validation":  validation_summary if not failed else {},
            "error":       error_message,
        }
