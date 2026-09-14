"""Schema + legacy-code references for the Legacy SQL Converter.

Prefers the data warehouse's OWN documented dictionary views —
`core.vw_data_dictionary` and `meta.vw_code_dictionary` (see the
Data-WareHoues project, migrations V031/V032) — since that's the sanctioned,
maintained interface for exactly this. Falls back to raw
`information_schema` introspection for a tenant that hasn't had that fleet
migration applied yet, so this tool still works everywhere in the meantime;
it will simply get better (richer descriptions, curated labels) as that
rollout completes, with no code change needed here.

Also dumps the ACTUAL VALUES of small core.dim_* lookup tables (config data,
not employee records) — resolving a legacy numeric code (a holiday type, a
shift id, a designation id) to its business meaning is the whole point of
this tool, and the dictionary views only carry schema, not row values.

Everything here is best-effort and read-only: a lookup failure (datamart
unreachable, a view or table not present) yields an empty reference for that
piece rather than failing the analysis.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.tenancy import TenantContext
from app.db.datamart import datamart_connection
from app.services.rule_report_ai.catalogue import build_catalogue_reference
from app.services.tenant_scope import resolve_datamart_key

log = get_logger(__name__)

# Postgres declarative-partition shards (fct_attendance_day_y2026, _default,
# fct_punch_202408, ...) — skip in favour of the parent/logical table.
_PARTITION_SHARD_RE = re.compile(r"_(y\d{4}|default|\d{6})$")
_CORE_TABLE_RE = re.compile(r"^(fct|dim)_")


def build_mart_reference(db: Session, tenant_id: str) -> str:
    """mart.* physical schema — the exact same source the generic Report
    Builder chat already uses (SemanticService), reused as-is here."""
    return build_catalogue_reference(db, tenant_id)


def build_core_schema_reference(ctx: TenantContext) -> str:
    """core.fct_*/core.dim_* schema (columns + labels/descriptions) — record-
    level detail a legacy report often needs that the mart doesn't carry."""
    try:
        datamart_key = resolve_datamart_key(ctx.tenant_id)
        with datamart_connection(ctx, datamart_key) as conn:
            rows = _query_core_dictionary_view(conn) or _query_core_information_schema(conn)
    except Exception as exc:  # noqa: BLE001 - best-effort, never fatal to an analysis run
        log.warning("legacy_sql_core_reference_failed", tenant_id=ctx.tenant_id, error=str(exc)[:200])
        return ""
    ref = format_core_reference(rows)
    if not ref:
        log.warning("legacy_sql_core_reference_empty", tenant_id=ctx.tenant_id, rows=len(rows))
    return ref


def _query_core_dictionary_view(conn) -> list[tuple] | None:
    try:
        rows = conn.execute(text(
            "SELECT object_name, field_name, COALESCE(label, field_name) "
            "FROM core.vw_data_dictionary ORDER BY object_name, ordinal_position"
        )).fetchall()
        return [tuple(r) for r in rows]
    except Exception:  # noqa: BLE001 - view not deployed yet for this tenant; fall back
        conn.rollback()
        return None


def _query_core_information_schema(conn) -> list[tuple]:
    rows = conn.execute(text(
        "SELECT table_name, column_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'core' ORDER BY table_name, ordinal_position"
    )).fetchall()
    return [(t, c, _humanize(c)) for t, c, _ in rows]


def _humanize(col: str) -> str:
    return col.replace("_", " ").title()


def format_core_reference(rows) -> str:
    """Pure formatting/filtering step, split out so it's unit-testable
    without a live connection."""
    by_table: dict[str, dict[str, str]] = {}
    for table_name, column_name, label in rows:
        if not _CORE_TABLE_RE.match(table_name) or _PARTITION_SHARD_RE.search(table_name):
            continue
        if column_name.startswith("_"):  # ETL bookkeeping (_loaded_at, _batch_id, _row_hash, ...)
            continue
        by_table.setdefault(table_name, {})[column_name] = label

    if not by_table:
        return ""

    lines = [
        ("core.* fact/dimension tables (record-level detail below the mart — "
         "use these for per-record fields, legacy status/type codes, and shift "
         "flags the mart summary tables don't carry):"),
    ]
    for table_name in sorted(by_table):
        lines.append(f"\ncore.{table_name}:")
        for column, label in sorted(by_table[table_name].items()):
            lines.append(f"  {column} — {label}")
    return "\n".join(lines)


# Small core.dim_* tables are lookup/config data (holiday types, shift
# definitions, designations, attendance groups, ...), not employee records —
# safe to include IN FULL so a legacy numeric code (holiday type 2, shift
# 132, designation 5, ...) resolves to its business meaning directly. A large
# dim table (dim_employee, dim_employee_version, dim_date, dim_org_node, ...)
# is excluded by the row cap — it isn't a code lookup.
_DIM_VALUE_MAX_ROWS = 250
# Exclude (not include-list) — a dim lookup table's meaningful columns vary
# too much per table (booleans like is_off_shift, rates, times, codes, names)
# to safely allowlist by name; drop only what's clearly not useful for
# resolving a legacy code (free-text/geo/contact fields) plus ETL bookkeeping.
_DIM_SKIP_COLUMN_RE = re.compile(r"(address|latitude|longitude|email|mobile_no|phone)$", re.I)


def build_dim_value_reference(ctx: TenantContext) -> str:
    """The actual row contents of small core.dim_* lookup tables — resolves a
    legacy numeric code to its business meaning. Independent of the
    dictionary views (those carry schema, not values)."""
    try:
        datamart_key = resolve_datamart_key(ctx.tenant_id)
        with datamart_connection(ctx, datamart_key) as conn:
            cols_rows = conn.execute(text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'core' AND table_name ~ '^dim_' "
                "ORDER BY table_name, ordinal_position"
            )).fetchall()
            tables: dict[str, list[str]] = {}
            for table_name, column_name in cols_rows:
                if _PARTITION_SHARD_RE.search(table_name):
                    continue
                tables.setdefault(table_name, []).append(column_name)

            blocks: list[str] = []
            for table_name, all_columns in sorted(tables.items()):
                value_cols = select_dim_value_columns(all_columns)
                if not value_cols:
                    continue
                count = conn.execute(text(f'SELECT count(*) FROM core."{table_name}"')).scalar()
                if count is None or count > _DIM_VALUE_MAX_ROWS:
                    continue
                col_list = ", ".join(f'"{c}"' for c in value_cols)
                value_rows = conn.execute(
                    text(f'SELECT {col_list} FROM core."{table_name}" ORDER BY 1')
                ).fetchall()
                block = format_dim_value_block(table_name, value_cols, value_rows)
                if block:
                    blocks.append(block)
    except Exception as exc:  # noqa: BLE001 - best-effort, never fatal to an analysis run
        log.warning("legacy_sql_dim_values_failed", tenant_id=ctx.tenant_id, error=str(exc)[:200])
        return ""

    if not blocks:
        log.warning("legacy_sql_dim_values_empty", tenant_id=ctx.tenant_id)
        return ""

    return "\n".join([
        ("Actual values in this tenant's small core.dim_* lookup tables (config "
         "data, not employee records) — resolve a legacy numeric code or ID "
         "directly against these:"),
        *blocks,
    ])


def select_dim_value_columns(all_columns: list[str]) -> list[str]:
    """Which of a dim table's columns are worth including in a value dump —
    pure, so it's unit-testable without a live connection."""
    return [c for c in all_columns if not c.startswith("_") and not _DIM_SKIP_COLUMN_RE.search(c)]


def format_dim_value_block(table_name: str, columns: list[str], rows) -> str:
    """Render one dim table's rows, dropping any column that's NULL in EVERY
    fetched row. Pure, so it's unit-testable without a live connection."""
    rows = [list(r) for r in rows]
    populated = [i for i, _ in enumerate(columns) if any(r[i] is not None for r in rows)]
    if not populated:
        return ""
    cols = [columns[i] for i in populated]
    lines = [f"\ncore.{table_name} ({', '.join(cols)}):"]
    for row in rows:
        lines.append("  " + ", ".join(f"{row[i]}" for i in populated))
    return "\n".join(lines)


def build_code_dictionary_reference(ctx: TenantContext) -> str:
    """`meta.code_map`/`meta.vw_code_dictionary` — legacy status codes with NO
    lookup table in the source at all (their meaning was hand-extracted from
    the old PHP application). Prefers the documented view; falls back to the
    raw table for a tenant that hasn't had that migration applied yet."""
    try:
        datamart_key = resolve_datamart_key(ctx.tenant_id)
        with datamart_connection(ctx, datamart_key) as conn:
            rows = _query_code_dictionary_view(conn) or _query_code_map_table(conn)
    except Exception as exc:  # noqa: BLE001 - best-effort, never fatal to an analysis run
        log.warning("legacy_sql_code_reference_failed", tenant_id=ctx.tenant_id, error=str(exc)[:200])
        return ""
    ref = format_code_dictionary_reference(rows)
    if not ref:
        log.warning("legacy_sql_code_reference_empty", tenant_id=ctx.tenant_id)
    return ref


def _query_code_dictionary_view(conn) -> list[tuple] | None:
    try:
        rows = conn.execute(text(
            "SELECT code_set, code_value, code_label, code_group FROM meta.vw_code_dictionary "
            "ORDER BY code_set, sort_order"
        )).fetchall()
        return [tuple(r) for r in rows]
    except Exception:  # noqa: BLE001 - view not deployed yet for this tenant; fall back
        conn.rollback()
        return None


def _query_code_map_table(conn) -> list[tuple]:
    rows = conn.execute(text(
        "SELECT code_set, code_value, code_label, code_group FROM meta.code_map "
        "WHERE is_active ORDER BY code_set, sort_order"
    )).fetchall()
    return [tuple(r) for r in rows]


def format_code_dictionary_reference(rows) -> str:
    """Pure formatting step, split out so it's unit-testable without a live
    connection."""
    if not rows:
        return ""
    by_set: dict[str, list[tuple]] = {}
    for code_set, code_value, code_label, code_group in rows:
        by_set.setdefault(code_set, []).append((code_value, code_label, code_group))

    lines = [
        ("Legacy status codes with NO lookup table in the source system (hand-"
         "extracted from the old application's source code — not derivable "
         "from warehouse data). The SAME code number can mean something "
         "different in a different code_set (e.g. 2 is not the same thing in "
         "LEAVE_STATUS as in SHORT_LIEU_LEAVE_STATUS) — match the code_set to "
         "whichever field the legacy SQL actually filters on:"),
    ]
    for code_set in sorted(by_set):
        lines.append(f"\n{code_set}:")
        for code_value, code_label, code_group in by_set[code_set]:
            group_suffix = f" ({code_group})" if code_group else ""
            lines.append(f"  {code_value} — {code_label}{group_suffix}")
    return "\n".join(lines)
