"""
Peek distinct column values so the LLM uses real warehouse literals in WHERE clauses.

Also detects zero-row results caused by guessed filter values (case / enum mismatch).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text as sa_text

from ..schema import _get_engine

logger = logging.getLogger("ai_services.datamart.column_value_peek")

_DISTINCT_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL_SEC = 300
_MAX_DISTINCT = 12
_MAX_TABLES = 4
_MAX_COLS_PER_TABLE = 3

_SAFE_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$", re.I)

# Semantic views that already encode a filter — extra WHERE on these often causes 0 rows.
PRE_FILTERED_VIEWS: dict[str, str] = {
    "vw_pending_leave_approvals": (
        "Already limited to pending approvals (approval_status_code = 'pending'). "
        "Do not add approval_status = 'Pending' or similar — omit that filter."
    ),
}

_CATEGORICAL_SKIP = (
    "name",
    "fullname",
    "email",
    "address",
    "reason",
    "description",
    "comment",
    "note",
    "date",
    "timestamp",
    "amount",
    "salary",
    "number",
    "emp_no",
)

_CATEGORICAL_HINT = re.compile(
    r"status|_code$|_type$|^type$|category|gender|frequency|level|state|flag",
    re.I,
)


def is_categorical_column(column: str) -> bool:
    c = (column or "").lower()
    if not c or not _SAFE_IDENT.match(c):
        return False
    if any(skip in c for skip in _CATEGORICAL_SKIP):
        return False
    return bool(_CATEGORICAL_HINT.search(c))


def peek_distinct_values(
    qualified_table: str,
    column: str,
    *,
    limit: int = _MAX_DISTINCT,
) -> list[str]:
    """Run a bounded SELECT DISTINCT for one column (read-only)."""
    if not qualified_table or "." not in qualified_table:
        return []
    schema, table = qualified_table.rsplit(".", 1)
    if not _SAFE_IDENT.match(schema) or not _SAFE_IDENT.match(table):
        return []
    if not _SAFE_IDENT.match(column):
        return []

    cache_key = f"{qualified_table.lower()}:{column.lower()}"
    now = time.time()
    cached = _DISTINCT_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL_SEC:
        return list(cached[1])

    sql = (
        f'SELECT DISTINCT "{column}" AS v '
        f'FROM "{schema}"."{table}" '
        f'WHERE "{column}" IS NOT NULL '
        f"ORDER BY 1 LIMIT {int(limit)}"
    )
    values: list[str] = []
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(sa_text("SET LOCAL statement_timeout = '8000'"))
                rows = conn.execute(sa_text(sql)).fetchall()
        for row in rows:
            if row[0] is None:
                continue
            values.append(str(row[0]))
    except Exception as exc:  # noqa: BLE001
        logger.debug("peek_distinct_values failed %s.%s: %s", qualified_table, column, exc)
        return []

    _DISTINCT_CACHE[cache_key] = (now, values)
    return values


def format_sample_values_block(
    columns_by_table: dict[str, list[str]],
    *,
    focus_tables: list[str] | None = None,
) -> str:
    """Build a prompt block with sample distinct values for categorical columns."""
    if not columns_by_table:
        return ""

    lines: list[str] = []
    table_items = list(columns_by_table.items())
    if focus_tables:
        focus_l = {t.lower() for t in focus_tables}
        table_items.sort(
            key=lambda kv: (
                0 if kv[0].rsplit(".", 1)[-1].lower() in focus_l else 1,
                kv[0],
            )
        )

    peeked_tables = 0
    for qualified, cols in table_items:
        if peeked_tables >= _MAX_TABLES:
            break
        short = qualified.rsplit(".", 1)[-1].lower()
        if short in PRE_FILTERED_VIEWS:
            lines.append(f"{qualified}\n  note: {PRE_FILTERED_VIEWS[short]}")
            peeked_tables += 1
            continue

        cat_cols = [c for c in cols if is_categorical_column(c)][: _MAX_COLS_PER_TABLE]
        if not cat_cols:
            continue

        table_lines: list[str] = []
        for col in cat_cols:
            vals = peek_distinct_values(qualified, col)
            if vals:
                shown = ", ".join(repr(v) for v in vals[:8])
                if len(vals) > 8:
                    shown += f", ... (+{len(vals) - 8} more)"
                table_lines.append(f"  {col} values: {shown}")

        if table_lines:
            lines.append(qualified)
            lines.extend(table_lines)
            peeked_tables += 1

    if not lines:
        return ""
    return "## Sample column values (use these literals in WHERE — exact spelling/case)\n" + "\n".join(lines)


@dataclass(frozen=True)
class FilterLiteral:
    column: str
    literal: str
    table_hint: str = ""


def extract_string_equality_literals(sql: str) -> list[FilterLiteral]:
    """Extract alias.column = 'value' or column = 'value' from SQL."""
    if not sql:
        return []
    out: list[FilterLiteral] = []
    for m in re.finditer(
        r"(?:\b(\w+)\.)?(\w+)\s*=\s*'([^']*)'",
        sql,
        flags=re.IGNORECASE,
    ):
        alias, col, literal = m.group(1) or "", m.group(2), m.group(3)
        if not literal.strip():
            continue
        out.append(FilterLiteral(column=col, literal=literal, table_hint=alias))
    return out


def _resolve_column_table(
    col: str,
    alias: str,
    columns_by_table: dict[str, list[str]],
) -> Optional[str]:
    col_l = col.lower()
    if alias:
        # Best-effort: alias often matches table abbreviation; scan all tables.
        pass
    matches = [
        q for q, cols in columns_by_table.items() if any(c.lower() == col_l for c in cols)
    ]
    if len(matches) == 1:
        return matches[0]
    if alias:
        alias_l = alias.lower()
        for q in matches:
            short = q.rsplit(".", 1)[-1].lower()
            if alias_l in short or short.startswith(alias_l):
                return q
    return matches[0] if matches else None


@dataclass
class ZeroRowFilterAnalysis:
    mismatches: list[tuple[FilterLiteral, list[str]]]
    prefiltered_view_note: str = ""

    @property
    def has_actionable_mismatch(self) -> bool:
        return bool(self.mismatches) or bool(self.prefiltered_view_note)

    def to_error_message(self) -> str:
        parts: list[str] = ["Query returned 0 rows — filter literal(s) may not exist in the warehouse."]
        if self.prefiltered_view_note:
            parts.append(self.prefiltered_view_note)
        for fl, vals in self.mismatches:
            parts.append(
                f"Column {fl.column} has values {vals[:6]!r} but SQL used {fl.literal!r}."
            )
        return " ".join(parts)

    def llm_guidance(self) -> str:
        lines = [
            "The SQL ran but returned 0 rows because a WHERE literal does not match stored values.",
            "Use ONLY literals from the Sample column values section (exact case/spelling).",
            "Prefer ILIKE '%keyword%' when unsure, or omit filters on pre-filtered semantic views.",
        ]
        for fl, vals in self.mismatches:
            if vals:
                lines.append(
                    f"For {fl.column}, use one of {vals[:5]!r} instead of {fl.literal!r}."
                )
        if self.prefiltered_view_note:
            lines.append(self.prefiltered_view_note)
        return " ".join(lines)


def analyze_zero_row_filters(
    sql: str,
    columns_by_table: dict[str, list[str]],
) -> Optional[ZeroRowFilterAnalysis]:
    """Detect guessed WHERE literals that do not exist in the column."""
    sql_l = (sql or "").lower()
    prefiltered_note = ""
    for view, note in PRE_FILTERED_VIEWS.items():
        if view in sql_l and re.search(
            rf"\b(?:approval_status|leave_status)\s*=\s*'",
            sql,
            re.I,
        ):
            prefiltered_note = note
            break

    mismatches: list[tuple[FilterLiteral, list[str]]] = []
    for fl in extract_string_equality_literals(sql):
        qualified = _resolve_column_table(fl.column, fl.table_hint, columns_by_table)
        if not qualified:
            continue
        vals = peek_distinct_values(qualified, fl.column)
        if not vals:
            continue
        if any(v.lower() == fl.literal.lower() for v in vals):
            continue
        # Literal not found — include if we have distinct values to suggest.
        mismatches.append((fl, vals))

    if not mismatches and not prefiltered_note:
        return None
    return ZeroRowFilterAnalysis(
        mismatches=mismatches,
        prefiltered_view_note=prefiltered_note,
    )
