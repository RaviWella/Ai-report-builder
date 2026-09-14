"""HR ETL extractors — source DB → PostgreSQL per-tenant staging.

Source: MintHRM MySQL or PostgreSQL (per tenant_registry.source_type).
Target: {tenant_id}_hr_raw schema in PostgreSQL.

Mirrors finance_etl/extractors.py pattern:
  - Full load: truncate + extract all rows
  - Incremental: watermark-based upsert
  - MySQL: keyset-chunked short queries (all staging tables with an id column)

Key MintHRM MySQL tables extracted:
  - employees (core employee master)
  - departments
  - designations / job titles
  - attendance / time records
  - leave requests + leave types
  - payroll runs + payroll details
  - performance reviews
  - training records
  - disciplinary records
  - org chart / reporting lines
"""
from __future__ import annotations

import datetime
import logging
import time
from contextvars import ContextVar
from typing import Any, Callable, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.services.hr_etl import control
from app.services.hr_etl.mysql_extract import (
    is_transient_mysql_error,
    wrap_keyset_chunk_sql,
)
from app.services.hr_etl.schema_names import raw_schema as _raw_schema_name
from app.services.hr_etl.source_connection import get_dialect
from app.services.hr_etl.staging_schema import ensure_staging_tables

logger = logging.getLogger("hr_etl")

BATCH_SIZE = settings.ETL_PG_BATCH_SIZE

# When set (non-empty), staging targets become stg_{table}__{suffix}
_staging_suffix: ContextVar[str] = ContextVar("etl_staging_suffix", default="")


def set_staging_suffix(suffix: str):
    return _staging_suffix.set(suffix or "")


def reset_staging_suffix(token) -> None:
    _staging_suffix.reset(token)


def resolve_staging_table(base_table: str) -> str:
    suffix = _staging_suffix.get()
    if not suffix:
        return base_table
    return f"{base_table}__{suffix}"


# ── Helpers ──────────────────────────────────────────────────────────

def _raw_schema(tenant_id: str) -> str:
    return _raw_schema_name(tenant_id)


def _ensure_staging_table(pg: Engine, tenant_id: str, table: str) -> None:
    """Clone structure from base stg_* table for multi-source suffix tables."""
    if "__" not in table:
        return
    base = table.split("__", 1)[0]
    schema = _raw_schema(tenant_id)
    with pg.begin() as conn:
        conn.execute(
            text(
                f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}" '
                f'(LIKE "{schema}"."{base}" INCLUDING ALL)'
            )
        )


def _truncate(pg: Engine, tenant_id: str, table: str) -> None:
    ensure_staging_tables(pg, tenant_id)
    schema = _raw_schema(tenant_id)
    _ensure_staging_table(pg, tenant_id, table)
    with pg.begin() as conn:
        conn.execute(
            text(f'TRUNCATE TABLE "{schema}".{table} RESTART IDENTITY CASCADE')
        )


def _bulk_insert(
    pg: Engine, tenant_id: str, table: str, columns: list[str], rows: list[dict]
) -> None:
    if not rows:
        return
    schema = _raw_schema(tenant_id)
    placeholders = ", ".join(f":{c}" for c in columns)
    cols_sql = ", ".join(columns)
    sql = f'INSERT INTO "{schema}".{table} ({cols_sql}) VALUES ({placeholders})'
    with pg.begin() as conn:
        conn.execute(text(sql), rows)


def _bulk_upsert(
    pg: Engine,
    tenant_id: str,
    table: str,
    columns: list[str],
    pk: str,
    rows: list[dict],
) -> None:
    if not rows:
        return
    schema = _raw_schema(tenant_id)
    placeholders = ", ".join(f":{c}" for c in columns)
    cols_sql = ", ".join(columns)
    update_cols = [c for c in columns if c != pk]
    update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    sql = (
        f'INSERT INTO "{schema}".{table} ({cols_sql}) VALUES ({placeholders})'
        f" ON CONFLICT ({pk}) DO UPDATE SET {update_sql}, extracted_at = NOW()"
    )
    with pg.begin() as conn:
        conn.execute(text(sql), rows)


def _persist_watermark(
    pg: Engine,
    tenant_id: str,
    table_name: str,
    *,
    watermark_col: str | None,
    max_watermark: Optional[datetime.datetime],
    rows: int,
    incremental: bool,
) -> None:
    """Record high-water mark after extract (incremental and full_load).

    Full loads previously skipped this, so the ETL Control UI stayed empty and
    the first incremental run could not filter by last_value.
    """
    if not watermark_col or rows <= 0:
        return

    mark: datetime.datetime | datetime.date | None = max_watermark
    if mark is None:
        mark = datetime.datetime.now(datetime.timezone.utc)
        logger.info(
            "watermark %s [%s]: no row timestamps; using run time (%s load)",
            table_name,
            tenant_id,
            "incremental" if incremental else "full",
        )
    elif isinstance(mark, datetime.date) and not isinstance(mark, datetime.datetime):
        mark = datetime.datetime.combine(mark, datetime.time.min, tzinfo=datetime.timezone.utc)
    elif isinstance(mark, datetime.datetime) and mark.tzinfo is None:
        mark = mark.replace(tzinfo=datetime.timezone.utc)

    control.set_watermark(pg, tenant_id, table_name, mark, rows)


def _watermark_as_datetime(val: object) -> datetime.datetime | None:
    """Coerce date/datetime watermark values to naive datetime for compare/store."""
    if isinstance(val, datetime.datetime):
        return val.replace(tzinfo=None) if val.tzinfo else val
    if isinstance(val, datetime.date):
        return datetime.datetime.combine(val, datetime.time.min)
    return None


def _resolve_wm_pg_col(
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
    watermark_col: str | None,
) -> Optional[str]:
    if not watermark_col:
        return None
    target = watermark_col.upper().split(".")[-1]
    for pg_col, _ in column_map:
        if pg_col.upper() == target:
            return pg_col
    return None


def _resolve_pk_column(
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
    pk_column: str | None,
) -> str | None:
    """Use explicit pk_column, else default to id when projected in column_map."""
    if pk_column:
        return pk_column
    if any(col == "id" for col, _ in column_map):
        return "id"
    return None


def _row_to_pg_dict(
    source_row: tuple[Any, ...],
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
) -> dict[str, Any]:
    pg_row: dict[str, Any] = {}
    for (pg_col, transform), src_val in zip(column_map, source_row):
        pg_row[pg_col] = transform(src_val) if transform else src_val
    return pg_row


def _max_staged_pk(
    pg: Engine, tenant_id: str, table: str, pk_column: str
) -> int:
    schema = _raw_schema(tenant_id)
    with pg.connect() as conn:
        val = conn.execute(
            text(f'SELECT COALESCE(MAX("{pk_column}"), 0) FROM "{schema}"."{table}"')
        ).scalar()
    return int(val or 0)


def _count_staged(pg: Engine, tenant_id: str, table: str) -> int:
    schema = _raw_schema(tenant_id)
    with pg.connect() as conn:
        val = conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        ).scalar()
    return int(val or 0)


def _flush_pg_batch(
    pg: Engine,
    tenant_id: str,
    target_table: str,
    pg_cols: list[str],
    batch: list[dict],
    *,
    incremental: bool,
    pk_column: str | None,
) -> None:
    if not batch:
        return
    if incremental and pk_column:
        _bulk_upsert(pg, tenant_id, target_table, pg_cols, pk_column, batch)
    else:
        _bulk_insert(pg, tenant_id, target_table, pg_cols, batch)


def _apply_incremental_filter(
    pg: Engine,
    source_sql: str,
    params: dict[str, Any],
    *,
    incremental: bool,
    pk_column: str | None,
    watermark_col: str | None,
    target_table: str,
    tenant_id: str,
    incremental_by_pk: bool = False,
) -> str:
    if not incremental:
        return source_sql
    inner = source_sql.rstrip().rstrip(";")
    if incremental_by_pk and pk_column:
        last_pk = _max_staged_pk(pg, tenant_id, target_table, pk_column)
        source_sql = (
            f"SELECT * FROM (\n{inner}\n) _etl_incr"
            f" WHERE {pk_column} > :_last_pk"
        )
        params["_last_pk"] = last_pk
        logger.info(
            "incremental %s [%s]: pk since %s=%d",
            target_table,
            tenant_id,
            pk_column,
            last_pk,
        )
        return source_sql
    if pk_column and watermark_col:
        wm = control.get_watermark(pg, tenant_id, target_table)
        if wm:
            source_sql = (
                f"SELECT * FROM (\n{inner}\n) _etl_incr"
                f" WHERE {watermark_col} > :_wm"
            )
            params["_wm"] = wm
            logger.info("incremental %s [%s]: since %s", target_table, tenant_id, wm)
        else:
            logger.info(
                "incremental %s [%s]: no watermark, initial load", target_table, tenant_id
            )
    else:
        logger.info(
            "incremental %s [%s]: full source scan (no watermark column)",
            target_table,
            tenant_id,
        )
    return source_sql


def _track_watermark(
    pg_row: dict[str, Any],
    wm_pg_col: str | None,
    max_watermark: Optional[datetime.datetime],
) -> Optional[datetime.datetime]:
    if not wm_pg_col or not pg_row.get(wm_pg_col):
        return max_watermark
    val_cmp = _watermark_as_datetime(pg_row[wm_pg_col])
    if val_cmp is None:
        return max_watermark
    if max_watermark is None or val_cmp > max_watermark:
        return val_cmp
    return max_watermark


def _stream_extract(
    source: Engine,
    pg: Engine,
    tenant_id: str,
    target_table: str,
    source_sql: str,
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
    *,
    incremental: bool = False,
    pk_column: str | None = None,
    watermark_col: str | None = None,
    incremental_by_pk: bool = False,
) -> int:
    """Extract rows from tenant source DB → PostgreSQL staging table.

    All MySQL staging extracts with an ``id`` column use keyset-chunked reads
    (short connections, retry/resume). Postgres keeps server-side streaming.

    ``incremental_by_pk`` loads only rows with ``id`` greater than the current
    staging high-water mark (for append-only sources without a reliable
    ``updated_at``).
    """
    target_table = resolve_staging_table(target_table)
    ensure_staging_tables(pg, tenant_id)
    params: dict[str, Any] = {}
    pk_column = _resolve_pk_column(column_map, pk_column)
    rows_before = _count_staged(pg, tenant_id, target_table) if incremental else 0
    source_sql = _apply_incremental_filter(
        pg,
        source_sql,
        params,
        incremental=incremental,
        pk_column=pk_column,
        watermark_col=watermark_col,
        target_table=target_table,
        tenant_id=tenant_id,
        incremental_by_pk=incremental_by_pk,
    )

    wm_pg_col = _resolve_wm_pg_col(column_map, watermark_col)
    is_mysql = get_dialect() == "mysql"
    use_chunked = is_mysql and pk_column is not None
    max_retries = settings.ETL_EXTRACT_MAX_RETRIES if is_mysql else 1
    retry_base = settings.ETL_EXTRACT_RETRY_BASE_SEC

    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_retries + 1):
        try:
            total, max_watermark = _run_extract_attempt(
                source,
                pg,
                tenant_id,
                target_table,
                source_sql,
                column_map,
                params,
                incremental=incremental,
                pk_column=pk_column,
                watermark_col=watermark_col,
                wm_pg_col=wm_pg_col,
                attempt=attempt,
                use_chunked=use_chunked,
            )
            if incremental:
                total = _count_staged(pg, tenant_id, target_table) - rows_before
            _persist_watermark(
                pg,
                tenant_id,
                target_table,
                watermark_col=watermark_col,
                max_watermark=max_watermark,
                rows=total,
                incremental=incremental,
            )
            mode = "incremental" if incremental else "full"
            logger.info(
                "extract %s [%s, %s]: %d rows", target_table, tenant_id, mode, total
            )
            return total
        except OperationalError as exc:
            last_exc = exc
            if not is_transient_mysql_error(exc) or attempt >= max_retries:
                raise
            delay = retry_base * (2 ** (attempt - 1))
            logger.warning(
                "extract %s [%s]: transient MySQL error (attempt %d/%d), "
                "retrying in %.1fs: %s",
                target_table,
                tenant_id,
                attempt,
                max_retries,
                delay,
                exc,
            )
            time.sleep(delay)

    if last_exc is not None:
        raise last_exc
    return 0


def _run_extract_attempt(
    source: Engine,
    pg: Engine,
    tenant_id: str,
    target_table: str,
    source_sql: str,
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
    params: dict[str, Any],
    *,
    incremental: bool,
    pk_column: str | None,
    watermark_col: str | None,
    wm_pg_col: str | None,
    attempt: int,
    use_chunked: bool,
) -> tuple[int, Optional[datetime.datetime]]:
    truncate_on_start = not incremental and attempt == 1
    if truncate_on_start:
        _truncate(pg, tenant_id, target_table)
    elif not incremental and attempt > 1 and not use_chunked:
        _truncate(pg, tenant_id, target_table)

    resume_after_id = 0
    if use_chunked and pk_column:
        if attempt > 1:
            resume_after_id = _max_staged_pk(pg, tenant_id, target_table, pk_column)
        elif incremental and params.get("_last_pk") is not None:
            # Align chunk cursor with pk-based incremental filter on first attempt.
            resume_after_id = int(params["_last_pk"])
        if resume_after_id:
            logger.info(
                "extract %s [%s]: resuming after %s=%d",
                target_table,
                tenant_id,
                pk_column,
                resume_after_id,
            )

    if use_chunked and pk_column:
        total, max_watermark = _chunked_extract_by_pk_with_wm(
            source,
            pg,
            tenant_id,
            target_table,
            source_sql,
            column_map,
            params,
            incremental=incremental,
            pk_column=pk_column,
            wm_pg_col=wm_pg_col,
            resume_after_id=resume_after_id,
        )
        return total, max_watermark

    total, max_watermark = _streaming_extract_with_wm(
        source,
        pg,
        tenant_id,
        target_table,
        source_sql,
        column_map,
        params,
        incremental=incremental,
        pk_column=pk_column,
        wm_pg_col=wm_pg_col,
    )
    return total, max_watermark


def _chunked_extract_by_pk_with_wm(
    source: Engine,
    pg: Engine,
    tenant_id: str,
    target_table: str,
    source_sql: str,
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
    params: dict[str, Any],
    *,
    incremental: bool,
    pk_column: str,
    wm_pg_col: str | None,
    resume_after_id: int,
) -> tuple[int, Optional[datetime.datetime]]:
    pg_cols = [c for c, _ in column_map]
    chunk_sql = wrap_keyset_chunk_sql(source_sql, pk_column)
    chunk_size = settings.ETL_MYSQL_CHUNK_SIZE
    last_pk = resume_after_id
    total = 0
    max_watermark: Optional[datetime.datetime] = None

    while True:
        chunk_params = {
            **params,
            "_chunk_after": last_pk,
            "_chunk_limit": chunk_size,
        }
        with source.connect() as src:
            rows = src.execute(text(chunk_sql), chunk_params).fetchall()
        if not rows:
            break

        batch: list[dict] = []
        chunk_high_pk = last_pk
        for source_row in rows:
            pg_row = _row_to_pg_dict(source_row, column_map)
            batch.append(pg_row)
            max_watermark = _track_watermark(pg_row, wm_pg_col, max_watermark)

            pk_val = pg_row.get(pk_column)
            if pk_val is not None:
                chunk_high_pk = max(chunk_high_pk, int(pk_val))

            if len(batch) >= BATCH_SIZE:
                _flush_pg_batch(
                    pg,
                    tenant_id,
                    target_table,
                    pg_cols,
                    batch,
                    incremental=incremental,
                    pk_column=pk_column,
                )
                total += len(batch)
                batch = []

        if batch:
            _flush_pg_batch(
                pg,
                tenant_id,
                target_table,
                pg_cols,
                batch,
                incremental=incremental,
                pk_column=pk_column,
            )
            total += len(batch)

        last_pk = chunk_high_pk
        if len(rows) < chunk_size:
            break

    return total, max_watermark


def _streaming_extract_with_wm(
    source: Engine,
    pg: Engine,
    tenant_id: str,
    target_table: str,
    source_sql: str,
    column_map: list[tuple[str, Callable[[Any], Any] | None]],
    params: dict[str, Any],
    *,
    incremental: bool,
    pk_column: str | None,
    wm_pg_col: str | None,
) -> tuple[int, Optional[datetime.datetime]]:
    pg_cols = [c for c, _ in column_map]
    total = 0
    batch: list[dict] = []
    max_watermark: Optional[datetime.datetime] = None

    with source.connect() as src:
        result = src.execution_options(stream_results=True).execute(
            text(source_sql), params
        )
        for source_row in result:
            pg_row = _row_to_pg_dict(source_row, column_map)
            batch.append(pg_row)
            max_watermark = _track_watermark(pg_row, wm_pg_col, max_watermark)

            if len(batch) >= BATCH_SIZE:
                _flush_pg_batch(
                    pg,
                    tenant_id,
                    target_table,
                    pg_cols,
                    batch,
                    incremental=incremental,
                    pk_column=pk_column,
                )
                total += len(batch)
                batch = []

    if batch:
        _flush_pg_batch(
            pg,
            tenant_id,
            target_table,
            pg_cols,
            batch,
            incremental=incremental,
            pk_column=pk_column,
        )
        total += len(batch)

    return total, max_watermark


# ── Common transforms ────────────────────────────────────────────────

def _int(v): return int(v) if v is not None else None
def _str(v): return str(v).strip() if v is not None else None
def _float(v): return float(v) if v is not None else None
def _bool(v): return bool(v) if v is not None else None
def _date(v): return v.date() if isinstance(v, datetime.datetime) else v


def _safe_date(v: object) -> datetime.date | None:
    """Map MySQL zero-dates to NULL for PostgreSQL."""
    if v is None:
        return None
    if isinstance(v, str) and v.startswith("0000"):
        return None
    if isinstance(v, datetime.datetime):
        if v.year < 1900:
            return None
        return v.date()
    if isinstance(v, datetime.date):
        if v.year < 1900:
            return None
        return v
    return _date(v)


def _safe_datetime(v: object) -> datetime.datetime | None:
    """Map MySQL zero-datetimes to NULL for PostgreSQL."""
    if v is None:
        return None
    if isinstance(v, str) and v.startswith("0000"):
        return None
    if isinstance(v, datetime.datetime):
        if v.year < 1900:
            return None
        return v
    if isinstance(v, datetime.date):
        return datetime.datetime.combine(v, datetime.time.min)
    return None


# ═══ Per-table extractors ════════════════════════════════════════════

def extract_employees(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """employees → stg_employees

    Core employee master — the spine of every HR metric.
    """
    sql = """
        SELECT
            id, employee_code, first_name, last_name, full_name,
            gender, date_of_birth, national_id, email, phone,
            department_id, designation_id, branch_id, cost_center_id,
            employment_type, employment_status,
            date_joined, date_confirmed, date_resigned, date_terminated,
            reporting_to, created_at, updated_at
        FROM employees
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_employees", sql,
        [
            ("id", _int),
            ("employee_code", _str),
            ("first_name", _str),
            ("last_name", _str),
            ("full_name", _str),
            ("gender", _str),
            ("date_of_birth", _date),
            ("national_id", _str),
            ("email", _str),
            ("phone", _str),
            ("department_id", _int),
            ("designation_id", _int),
            ("branch_id", _int),
            ("cost_center_id", _int),
            ("employment_type", _str),
            ("employment_status", _str),
            ("date_joined", _date),
            ("date_confirmed", _date),
            ("date_resigned", _date),
            ("date_terminated", _date),
            ("reporting_to", _int),
            ("created_at", None),
            ("updated_at", None),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_departments(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """departments → stg_departments"""
    sql = """
        SELECT id, code, name, parent_id, head_employee_id,
               is_active, created_at, updated_at
        FROM departments
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_departments", sql,
        [
            ("id", _int), ("code", _str), ("name", _str),
            ("parent_id", _int), ("head_employee_id", _int),
            ("is_active", _bool), ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_designations(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """designations → stg_designations"""
    sql = """
        SELECT id, code, title, grade, department_id,
               is_active, created_at, updated_at
        FROM designations
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_designations", sql,
        [
            ("id", _int), ("code", _str), ("title", _str),
            ("grade", _str), ("department_id", _int),
            ("is_active", _bool), ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_branches(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """branches → stg_branches"""
    sql = """
        SELECT id, code, name, region, country,
               is_active, created_at, updated_at
        FROM branches
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_branches", sql,
        [
            ("id", _int), ("code", _str), ("name", _str),
            ("region", _str), ("country", _str),
            ("is_active", _bool), ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_attendance(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """attendance_records → stg_attendance"""
    sql = """
        SELECT id, employee_id, attendance_date, check_in, check_out,
               status, late_minutes, early_leave_minutes,
               overtime_minutes, work_hours, shift_id,
               created_at, updated_at
        FROM attendance_records
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_attendance", sql,
        [
            ("id", _int), ("employee_id", _int),
            ("attendance_date", _date), ("check_in", None), ("check_out", None),
            ("status", _str), ("late_minutes", _int), ("early_leave_minutes", _int),
            ("overtime_minutes", _int), ("work_hours", _float), ("shift_id", _int),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_leave_requests(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """leave_requests → stg_leave_requests"""
    sql = """
        SELECT id, employee_id, leave_type_id, start_date, end_date,
               days_requested, days_approved, status, approved_by,
               reason, created_at, updated_at
        FROM leave_requests
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_requests", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("start_date", _date), ("end_date", _date),
            ("days_requested", _float), ("days_approved", _float),
            ("status", _str), ("approved_by", _int), ("reason", _str),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_leave_types(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    """leave_types → stg_leave_types (full reload — small lookup)"""
    sql = """
        SELECT id, code, name, is_paid, max_days_per_year,
               carry_forward, is_active, created_at, updated_at
        FROM leave_types
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_types", sql,
        [
            ("id", _int), ("code", _str), ("name", _str),
            ("is_paid", _bool), ("max_days_per_year", _float),
            ("carry_forward", _bool), ("is_active", _bool),
            ("created_at", None), ("updated_at", None),
        ],
    )


def extract_payroll_runs(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """payroll_runs → stg_payroll_runs"""
    sql = """
        SELECT id, run_code, payroll_month, payroll_year,
               status, total_gross, total_deductions, total_net,
               processed_by, processed_at, created_at, updated_at
        FROM payroll_runs
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_runs", sql,
        [
            ("id", _int), ("run_code", _str),
            ("payroll_month", _int), ("payroll_year", _int),
            ("status", _str),
            ("total_gross", _float), ("total_deductions", _float), ("total_net", _float),
            ("processed_by", _int), ("processed_at", None),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_payroll_details(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """payroll_details → stg_payroll_details (per-employee per-run)"""
    sql = """
        SELECT id, payroll_run_id, employee_id,
               basic_salary, allowances, overtime_pay, bonuses,
               gross_salary, tax_deduction, other_deductions,
               net_salary, created_at, updated_at
        FROM payroll_details
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_details", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("basic_salary", _float), ("allowances", _float),
            ("overtime_pay", _float), ("bonuses", _float),
            ("gross_salary", _float), ("tax_deduction", _float),
            ("other_deductions", _float), ("net_salary", _float),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_performance_reviews(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """performance_reviews → stg_performance_reviews"""
    sql = """
        SELECT id, employee_id, reviewer_id, review_period,
               review_year, overall_score, rating, status,
               review_date, created_at, updated_at
        FROM performance_reviews
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_performance_reviews", sql,
        [
            ("id", _int), ("employee_id", _int), ("reviewer_id", _int),
            ("review_period", _str), ("review_year", _int),
            ("overall_score", _float), ("rating", _str), ("status", _str),
            ("review_date", _date), ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


def extract_training_records(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """training_records → stg_training_records"""
    sql = """
        SELECT id, employee_id, training_id, training_name,
               training_type, start_date, end_date, status,
               score, cost, created_at, updated_at
        FROM training_records
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_training_records", sql,
        [
            ("id", _int), ("employee_id", _int), ("training_id", _int),
            ("training_name", _str), ("training_type", _str),
            ("start_date", _date), ("end_date", _date),
            ("status", _str), ("score", _float), ("cost", _float),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental, pk_column="id", watermark_col="updated_at",
    )


# ── Extractor registry ───────────────────────────────────────────────

EXTRACTORS: list[tuple[str, Callable]] = [
    ("stg_branches",            extract_branches),
    ("stg_departments",         extract_departments),
    ("stg_designations",        extract_designations),
    ("stg_leave_types",         extract_leave_types),
    ("stg_employees",           extract_employees),
    ("stg_attendance",          extract_attendance),
    ("stg_leave_requests",      extract_leave_requests),
    ("stg_payroll_runs",        extract_payroll_runs),
    ("stg_payroll_details",     extract_payroll_details),
    ("stg_performance_reviews", extract_performance_reviews),
    ("stg_training_records",    extract_training_records),
]

# Tables that support incremental mode
INCREMENTAL_TABLES: set[str] = {
    "stg_employees",
    "stg_attendance",
    "stg_leave_requests",
    "stg_payroll_runs",
    "stg_payroll_details",
    "stg_performance_reviews",
    "stg_training_records",
    "stg_departments",
    "stg_designations",
    "stg_branches",
}
