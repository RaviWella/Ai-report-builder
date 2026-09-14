"""Deterministic checks: does generated SQL align with the question and schema links?"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp

from ..semantic.column_projection import is_join_only_column
from ..config import MAX_RESULT_ROWS
from ..llm.llm_response import is_non_executable_sql
from ..schema_broker import SchemaGrounding
from ..orchestration.schema_linker import SchemaLink
from ..domain_sql.metric_templates import question_wants_row_detail, is_scalar_aggregate_sql
from ..validation.validation_models import GenerationValidation


_TOP_N_RE = re.compile(
    r"\b(?:top|first|highest|lowest|bottom)\s+(\d+)\b",
    re.IGNORECASE,
)
_RANKING_RE = re.compile(
    r"\b(?:top|highest|lowest|most|least|best|worst|rank)\b",
    re.IGNORECASE,
)


def _extract_limit(tree: exp.Expression) -> Optional[int]:
    for node in tree.find_all(exp.Limit):
        val = node.expression
        if isinstance(val, exp.Literal) and val.is_int:
            return int(val.this)
        if isinstance(val, exp.Cast) and isinstance(val.this, exp.Literal) and val.this.is_int:
            return int(val.this.this)
    return None


def _table_count(tree: exp.Expression) -> int:
    names: set[str] = set()
    for table in tree.find_all(exp.Table):
        if table.name:
            names.add(table.name.lower())
    return len(names)


def _has_order_by(tree: exp.Expression) -> bool:
    return bool(list(tree.find_all(exp.Order)))


def _has_cross_join(tree: exp.Expression) -> bool:
    for join in tree.find_all(exp.Join):
        if join.kind and str(join.kind).upper() == "CROSS":
            return True
    return False


def _outer_select_projections(tree: exp.Expression) -> list[str]:
    """Unqualified output column names from the outermost SELECT (aliases preferred)."""
    # Select is a subclass of Query in sqlglot — check Select first.
    if isinstance(tree, exp.Select):
        select = tree
    elif isinstance(tree, exp.Query) and isinstance(tree.this, exp.Select):
        select = tree.this
    else:
        return []
    names: list[str] = []
    for expr in select.expressions:
        if isinstance(expr, exp.Star):
            names.append("*")
            continue
        if isinstance(expr, exp.Alias) and expr.alias:
            names.append(str(expr.alias))
            continue
        if isinstance(expr, exp.Column) and expr.name:
            names.append(str(expr.name))
            continue
        if hasattr(expr, "name") and expr.name:
            names.append(str(expr.name))
    return names


def _join_only_in_select_warnings(
    tree: exp.Expression,
    grounding: SchemaGrounding,
) -> list[str]:
    """Warn when technical keys are projected to the user-facing result set."""
    projected = _outer_select_projections(tree)
    if "*" in projected:
        return []

    table_cols: dict[str, list[str]] = {}
    for qualified, cols in grounding.columns_by_table.items():
        short = qualified.rsplit(".", 1)[-1].lower()
        table_cols[short] = cols

    warnings: list[str] = []
    for name in projected:
        col = name.lower()
        if not col:
            continue
        for cols in table_cols.values():
            if col not in {c.lower() for c in cols}:
                continue
            if is_join_only_column(col, cols):
                warnings.append(
                    f"SELECT projects join key `{name}`; use a name/code column for display "
                    "(keep keys in JOIN/WHERE only)."
                )
                break
    return warnings


def check_sql_faithfulness(
    *,
    question: str,
    sql: str,
    grounding: SchemaGrounding,
    schema_links: list[SchemaLink],
    binding_passed: bool,
) -> GenerationValidation:
    warnings: list[str] = []
    binding: str = "passed" if binding_passed else "failed"

    if is_non_executable_sql(sql):
        warnings.append(
            "No executable SQL was produced (NONE or empty). Use the workforce mart "
            "or grounded columns — do not refuse detail reports with SQL:NONE."
        )
        return GenerationValidation(binding=binding, warnings=warnings)

    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Faithfulness check could not parse SQL: {exc}")
        return GenerationValidation(binding=binding, warnings=warnings)

    top_m = _TOP_N_RE.search(question)
    if top_m:
        expected_n = int(top_m.group(1))
        limit_n = _extract_limit(tree)
        if limit_n is None:
            warnings.append(
                f"Question asks for top {expected_n} but SQL has no LIMIT clause."
            )
        elif limit_n > expected_n:
            warnings.append(
                f"Question asks for top {expected_n} but SQL uses LIMIT {limit_n}."
            )

    if _RANKING_RE.search(question) and not _has_order_by(tree):
        warnings.append("Ranking question but SQL has no ORDER BY.")

    if _table_count(tree) >= 2:
        unqualified = [
            c.name
            for c in tree.find_all(exp.Column)
            if c.name and c.name != "*" and not c.table
        ]
        if len(unqualified) >= 2:
            warnings.append(
                "Multiple tables in SQL but some columns are unqualified; "
                "ambiguous column resolution is possible."
            )
        if _has_cross_join(tree):
            warnings.append("SQL uses CROSS JOIN; verify join keys match the question intent.")

    warnings.extend(_join_only_in_select_warnings(tree, grounding))

    if question_wants_row_detail(question) and is_scalar_aggregate_sql(sql):
        warnings.append(
            "Question asks for a detailed report with multiple fields, but SQL only "
            "returns a single aggregate (e.g. COUNT). Use the LLM path with full grounding."
        )

    high_links = [lk for lk in schema_links if lk.confidence == "high" and lk.qualified_column]
    if high_links:
        sql_lower = sql.lower()
        for link in high_links:
            col = link.qualified_column.rsplit(".", 1)[-1].lower()
            if col and col not in sql_lower:
                warnings.append(
                    f"Catalog maps '{link.term}' to {link.qualified_column} "
                    "but that column does not appear in SQL."
                )

    return GenerationValidation(
        binding=binding,  # type: ignore[arg-type]
        warnings=warnings,
        truncated=False,
        grounding_expanded=False,
    )
