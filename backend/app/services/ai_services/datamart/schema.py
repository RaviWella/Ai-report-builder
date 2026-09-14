"""
Datamart AI Service — warehouse introspection and SQL execution.

Uses DatamartRuntimeContext when set (per-tenant / multi-schema); otherwise falls
back to legacy DATAMART_DB_* + WAREHOUSE_SCHEMA for backward compatibility.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Optional

from sqlalchemy import create_engine, inspect as sa_inspect, text

if TYPE_CHECKING:
    from .schema_broker import SchemaGrounding
from sqlalchemy.engine import Engine

from .config import (
    DATAMART_DEFAULT_TENANT_ID,
    DATAMART_METADATA_CACHE_TTL_SEC,
    DATAMART_TABLE_LIST_CACHE_TTL_SEC,
    MAX_RESULT_ROWS,
    WAREHOUSE_DATABASE_URL,
    WAREHOUSE_STATEMENT_TIMEOUT_SEC,
)
from .sql.sql_exec_guard import is_warehouse_timeout_error
from .workspace.runtime_context import (
    DatamartRuntimeContext,
    get_datamart_context,
    require_datamart_context,
    resolve_datamart_context,
)

logger = logging.getLogger("ai_services.datamart")

# When warehouse introspection returns zero columns (empty table / permissions),
# use semantic-catalog columns so join templates and Tier A SQL still work.
_CATALOG_INTROSPECTION_FALLBACK: dict[str, list[str]] = {
    "fct_salary_bank_instruction": [
        "employee_sk",
        "source_bank_id",
        "source_bank_branch_id",
        "bank_passbook_name",
        "account_number",
        "bank_amount",
    ],
    "dim_bank": ["bank_sk", "source_bank_id", "bank_code", "bank_name"],
    "dim_bank_branch": [
        "bank_branch_sk",
        "source_bank_branch_id",
        "source_bank_id",
        "branch_name",
    ],
    "dim_shift": ["shift_sk", "source_shift_id", "shift_name", "is_current"],
}


def _columns_with_catalog_fallback(
    schema: str,
    table: str,
    cols: list[str],
) -> list[str]:
    if cols:
        return cols
    fallback = _CATALOG_INTROSPECTION_FALLBACK.get(table.lower())
    if fallback:
        logger.info(
            "Using catalog column fallback for %s.%s (%d cols)",
            schema,
            table,
            len(fallback),
        )
        return list(fallback)
    return []


_legacy_engine: Optional[Engine] = None
_warehouse_table_list_cache: dict[str, tuple[float, list[str]]] = {}
_column_introspect_cache: dict[str, tuple[float, list[str]]] = {}


def clear_warehouse_table_list_cache() -> None:
    _warehouse_table_list_cache.clear()
    _column_introspect_cache.clear()


def _legacy_engine() -> Engine:
    global _legacy_engine
    if _legacy_engine is None:
        from .workspace.runtime_context import _warehouse_engine_connect_args

        _legacy_engine = create_engine(
            WAREHOUSE_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
            connect_args=_warehouse_engine_connect_args(),
        )
        logger.debug("Legacy warehouse engine created: %s", WAREHOUSE_DATABASE_URL)
    return _legacy_engine


def _active_context() -> DatamartRuntimeContext:
    ctx = get_datamart_context()
    if ctx is not None:
        return ctx
    return resolve_datamart_context(DATAMART_DEFAULT_TENANT_ID)


def _get_engine() -> Engine:
    return _active_context().engine


def _query_schemas(ctx: DatamartRuntimeContext) -> tuple[str, ...]:
    return ctx.query_schemas


def relations_in_schema(inspector, schema: str) -> list[str]:
    """Base tables and views in a schema (hr_semantic is view-only)."""
    seen: set[str] = set()
    out: list[str] = []
    for getter_name in ("get_table_names", "get_view_names"):
        getter = getattr(inspector, getter_name, None)
        if getter is None:
            continue
        try:
            for name in getter(schema=schema):
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s failed for %s: %s", getter_name, schema, exc)
    return out


def _tables_in_schema(inspector, schema: str) -> list[str]:
    return relations_in_schema(inspector, schema)


def _locate_short_table(
    inspector,
    short_name: str,
    schemas: tuple[str, ...],
) -> Optional[tuple[str, str]]:
    """Find schema.table for a short name without scanning the full warehouse."""
    key = short_name.lower()
    for schema in schemas:
        for rel in relations_in_schema(inspector, schema):
            if rel.lower() == key:
                return schema, rel
    return None


def _fetch_columns(
    engine: Engine,
    schema: str,
    table: str,
    *,
    cache_key: Optional[str] = None,
) -> list[str]:
    if cache_key:
        now = time.time()
        cached = _column_introspect_cache.get(cache_key)
        if cached and (now - cached[0]) < DATAMART_METADATA_CACHE_TTL_SEC:
            return list(cached[1])
    try:
        inspector = sa_inspect(engine)
        columns = inspector.get_columns(table, schema=schema)
        cols = [col["name"] for col in columns if col.get("name")]
        if cache_key and cols:
            _column_introspect_cache[cache_key] = (time.time(), cols)
        return cols
    except Exception as exc:  # noqa: BLE001
        logger.debug("introspect skip %s.%s: %s", schema, table, exc)
        return []


def _build_table_index(
    inspector,
    schemas: tuple[str, ...],
) -> dict[str, tuple[str, str]]:
    """Map lower(table) -> (schema, actual_table_name)."""
    index: dict[str, tuple[str, str]] = {}
    for schema in schemas:
        for table in _tables_in_schema(inspector, schema):
            key = table.lower()
            if key not in index:
                index[key] = (schema, table)
    return index


def _resolve_short_names(
    table_names: Optional[list[str]],
    index: dict[str, tuple[str, str]],
    schemas: tuple[str, ...],
) -> list[tuple[str, str]]:
    if not table_names:
        out: list[tuple[str, str]] = []
        seen_pairs: set[str] = set()
        for schema, table in index.values():
            key = f"{schema}.{table}".lower()
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            out.append((schema, table))
        return out

    allowed_schemas = {s.lower() for s in schemas}
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in table_names:
        name = (raw or "").strip()
        if not name:
            continue
        if "." in name:
            parts = name.split(".", 1)
            schema_part, short = parts[0].strip(), parts[1].strip()
            if schema_part.lower() in allowed_schemas and short:
                key = f"{schema_part}.{short}".lower()
                if key not in seen:
                    seen.add(key)
                    ordered.append((schema_part, short))
            continue
        actual = index.get(name.lower())
        if actual and actual[0] not in {f"{s}.{t}".lower() for s, t in ordered}:
            key = f"{actual[0]}.{actual[1]}".lower()
            if key not in seen:
                seen.add(key)
                ordered.append(actual)
    return ordered


def get_schema_info(
    table_names: Optional[list[str]] = None,
    *,
    max_total_chars: Optional[int] = None,
) -> str:
    try:
        ctx = _active_context()
        engine = ctx.engine
        inspector = sa_inspect(engine)
        schemas = _query_schemas(ctx)
        index = _build_table_index(inspector, schemas)
        to_describe = _resolve_short_names(table_names, index, schemas)

        schema_parts: list[str] = []
        footer = ""

        for schema, table in to_describe:
            try:
                columns = inspector.get_columns(table, schema=schema)
                col_defs = ", ".join(
                    f"{col['name']} ({str(col['type'])})" for col in columns
                )
                chunk = f"Table: {schema}.{table}\n  Columns: {col_defs}"
                if max_total_chars is not None and schema_parts:
                    joined = "\n\n".join(schema_parts)
                    if len(joined) + len(chunk) + 4 > max_total_chars:
                        omitted = len(to_describe) - len(schema_parts)
                        footer = (
                            f"\n\n[Schema truncated: {omitted} more table(s) omitted "
                            "for context limits.]"
                        )
                        break
                schema_parts.append(chunk)
            except Exception as col_exc:  # noqa: BLE001
                logger.debug("Could not introspect %s.%s: %s", schema, table, col_exc)

        text = "\n\n".join(schema_parts) + footer
        if max_total_chars is not None and len(text) > max_total_chars:
            return text[:max_total_chars].rstrip() + "\n\n[Schema description truncated.]"
        return text

    except Exception as exc:  # noqa: BLE001
        logger.error("Schema introspection failed: %s", exc)
        return ""


def introspect_table_columns(
    table_names: Optional[list[str]] = None,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    try:
        ctx = _active_context()
        engine = ctx.engine
        inspector = sa_inspect(engine)
        schemas = _query_schemas(ctx)

        if table_names:
            to_read: list[tuple[str, str]] = []
            allowed_schemas = {s.lower() for s in schemas}
            seen_pairs: set[str] = set()
            for raw in table_names:
                name = (raw or "").strip()
                if not name:
                    continue
                if "." in name:
                    parts = name.split(".", 1)
                    schema_part, short = parts[0].strip(), parts[1].strip()
                    if schema_part.lower() in allowed_schemas and short:
                        key = f"{schema_part}.{short}".lower()
                        if key not in seen_pairs:
                            seen_pairs.add(key)
                            to_read.append((schema_part, short))
                    continue
                located = _locate_short_table(inspector, name, schemas)
                if located:
                    key = f"{located[0]}.{located[1]}".lower()
                    if key not in seen_pairs:
                        seen_pairs.add(key)
                        to_read.append(located)
        else:
            index = _build_table_index(inspector, schemas)
            to_read = _resolve_short_names(None, index, schemas)

        if not to_read:
            return out

        ctx = _active_context()
        cache_prefix = f"{ctx.tenant_id}:{','.join(ctx.query_schemas)}"

        if len(to_read) == 1:
            schema, table = to_read[0]
            cache_key = f"{cache_prefix}:{schema}.{table}"
            cols = _columns_with_catalog_fallback(
                schema,
                table,
                _fetch_columns(engine, schema, table, cache_key=cache_key),
            )
            if cols:
                out[f"{schema}.{table}"] = cols
            return out

        max_workers = min(6, len(to_read))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _fetch_columns,
                    engine,
                    schema,
                    table,
                    cache_key=f"{cache_prefix}:{schema}.{table}",
                ): (schema, table)
                for schema, table in to_read
            }
            for fut in as_completed(futures):
                schema, table = futures[fut]
                cols = _columns_with_catalog_fallback(schema, table, fut.result())
                if cols:
                    out[f"{schema}.{table}"] = cols
    except Exception as exc:  # noqa: BLE001
        logger.error("introspect_table_columns failed: %s", exc)
    return out


def list_warehouse_tables() -> list[str]:
    """
    Unqualified table short names across all query schemas.

    vw_* in hr_semantic are listed first for broker ranking preference.
    """
    try:
        ctx = _active_context()
        cache_key = f"{ctx.tenant_id}:{','.join(ctx.query_schemas)}"
        now = time.time()
        cached = _warehouse_table_list_cache.get(cache_key)
        if cached and (now - cached[0]) < DATAMART_TABLE_LIST_CACHE_TTL_SEC:
            return list(cached[1])

        inspector = sa_inspect(ctx.engine)
        semantic_views: list[str] = []
        other: list[str] = []
        seen: set[str] = set()

        for schema in _query_schemas(ctx):
            for table in _tables_in_schema(inspector, schema):
                key = f"{schema}.{table}".lower()
                if key in seen:
                    continue
                seen.add(key)
                if schema == ctx.primary_schema and table.lower().startswith("vw_"):
                    semantic_views.append(table)
                else:
                    other.append(table)
        result = semantic_views + other
        _warehouse_table_list_cache[cache_key] = (now, result)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("list_warehouse_tables failed: %s", exc)
        return []


def _grounding_for_execute(
    sql: str,
    explicit: Optional["SchemaGrounding"] = None,
) -> Optional["SchemaGrounding"]:
    """Live introspection for tables referenced in SQL (pre-execute column gate)."""
    if explicit is not None and explicit.columns_by_table:
        return explicit
    from .schema_broker import SchemaGrounding, _finalize_grounding
    from .sql.sql_refs import warehouse_table_names_from_sql

    shorts = warehouse_table_names_from_sql(sql)
    if not shorts:
        return None
    g = _finalize_grounding(
        list(shorts),
        semantics_prompt_block="",
        source="pre_exec",
    )
    return g if g.columns_by_table else None


def execute_sql(
    sql: str,
    grounding: Optional["SchemaGrounding"] = None,
    *,
    validate_binding: bool = True,
) -> tuple[list[str], list[list], int]:
    from sqlalchemy import text as sa_text

    from .llm.llm_response import is_non_executable_sql
    from .sql.sql_table_normalize import rewrite_semantic_view_schema, strip_database_catalog_prefix

    if is_non_executable_sql(sql):
        raise RuntimeError(
            "Cannot execute SQL: query is missing or set to NONE. "
            "Generate a SELECT against the grounded schema first."
        )

    sql = strip_database_catalog_prefix(sql)
    sql = rewrite_semantic_view_schema(sql)

    from .sql.sql_column_allowlist import try_rewrite_unknown_columns
    from .sql.sql_exec_guard import validate_sql_against_grounding

    effective_grounding = _grounding_for_execute(sql, grounding) if validate_binding else None
    if effective_grounding is not None:
        bind_err = validate_sql_against_grounding(sql, effective_grounding)
        if bind_err:
            rewritten = try_rewrite_unknown_columns(sql, effective_grounding)
            if rewritten:
                bind_err = validate_sql_against_grounding(rewritten, effective_grounding)
                if not bind_err:
                    sql = rewritten
            if bind_err:
                raise RuntimeError(
                    f"SQL uses columns not in the warehouse allowlist: {bind_err}"
                )

    timeout_sec = max(5, WAREHOUSE_STATEMENT_TIMEOUT_SEC)
    preview = " ".join(sql.split())[:240]

    try:
        engine = _get_engine()
        t0 = time.perf_counter()
        logger.info(
            "warehouse execute start timeout_sec=%d sql_preview=%s",
            timeout_sec,
            preview,
        )
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    sa_text(f"SET LOCAL statement_timeout = '{int(timeout_sec * 1000)}'")
                )
                result = conn.execute(sa_text(sql))
                columns = list(result.keys())
                raw_rows = result.fetchmany(MAX_RESULT_ROWS + 1)

        rows = [_serialise_row(row) for row in raw_rows[:MAX_RESULT_ROWS]]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "warehouse execute done ms=%d rows=%d cols=%d",
            elapsed_ms,
            len(rows),
            len(columns),
        )
        return columns, rows, len(rows)

    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        logger.error("SQL execution failed: %s", msg)
        if is_warehouse_timeout_error(msg):
            raise RuntimeError(
                f"Warehouse query timed out after {timeout_sec}s. "
                "Try a narrower question, add filters, or increase "
                "DATAMART_WAREHOUSE_STATEMENT_TIMEOUT_SEC."
            ) from exc
        raise RuntimeError(msg) from exc


def _serialise_row(row) -> list:
    import datetime
    import decimal

    result = []
    for value in row:
        if isinstance(value, (datetime.date, datetime.datetime)):
            result.append(value.isoformat())
        elif isinstance(value, decimal.Decimal):
            result.append(float(value))
        elif value is None:
            result.append(None)
        else:
            result.append(value)
    return result
