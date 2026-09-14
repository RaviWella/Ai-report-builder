"""
Datamart AI Service — Post-Processing Engine
=============================================
Applies Python-level transformations to SQL result sets.

This handles calculations that cannot be expressed in a single SQL query:
  - add_percentage_column  : add col = (value / total) * 100
  - append_aggregate_row   : append a summary row (SUM, AVG, MIN, MAX, COUNT)
  - append_per_group_aggregate_rows : append one summary row per distinct group value
  - add_derived_column     : add col = expression evaluated per row

Each step is a dict with a "type" key and type-specific parameters.
The full config is stored in datamart_chat_messages.post_process_config
so results are always reproducible when re-running historical queries.

Public API
----------
    apply(columns, rows, config) -> (columns, rows)

    config is a list[dict] — each dict is one step.
    Returns the transformed columns and rows.
    Raises ValueError on invalid config.

Supported step types
--------------------
add_percentage_column:
    {
        "type": "add_percentage_column",
        "source_column": "salary",          # column to compute % of
        "new_column": "salary_pct",         # name of new column
        "label": "% of Total"               # display label (optional)
    }
    Adds a new column: row[source_column] / sum(all source_column) * 100

append_aggregate_row:
    {
        "type": "append_aggregate_row",
        "aggregations": {
            "salary": "AVG",                # column → function (SUM/AVG/MIN/MAX/COUNT)
            "employee_no": "COUNT"
        },
        "label_column": "employee_no",      # column to put the label in
        "label": "Average"                  # label text
    }
    Appends a single summary row at the bottom of the result.

append_per_group_aggregate_rows:
    {
        "type": "append_per_group_aggregate_rows",
        "group_column": "pay_group_name",
        "aggregations": {"current_basic_salary": "AVG"},
        "label_column": "employee_name",
        "label_format": "Branch average ({group})"
    }
    After the detail rows, appends one row per distinct value in ``group_column``.
    ``label_format`` must include ``{group}``; it becomes the text in ``label_column``.
    Aggregations are computed within each group over data rows only (prior summary
    rows in ``label_column`` are ignored, same as append_aggregate_row).

add_derived_column:
    {
        "type": "add_derived_column",
        "new_column": "salary_band",
        "expression": "HIGH if row['salary'] > 100000 else LOW",
        "label": "Salary Band"
    }
    Adds a new column computed from a safe expression per row.
    Only a restricted set of operations is allowed (no exec/eval of arbitrary code).
"""
import logging
import math
import re
from typing import Any, Optional

from ..config import (
    MAX_DATAMART_OUTPUT_ROWS,
    MAX_RESULT_ROWS,
    POST_PROCESS_APPEND_HEADROOM,
)

logger = logging.getLogger("ai_services.datamart")

# ── SQL helpers (used by agent + HTTP re-execute) ─────────────────


def shrink_outer_limit_for_append_sql(
    sql: str, post_process_config: Optional[list[dict[str, Any]]]
) -> str:
    """
    When post-processing will append rows, shrink the final ``LIMIT n`` so
    ``n + appended`` fits the datamart output budget (see ``MAX_DATAMART_OUTPUT_ROWS``).
    """
    if not post_process_config:
        return sql
    if not any(
        (step or {}).get("type")
        in ("append_aggregate_row", "append_per_group_aggregate_rows")
        for step in post_process_config
    ):
        return sql
    text = sql.strip()
    m = re.search(r"\bLIMIT\s+(\d+)\s*(;)?\s*\Z", text, flags=re.IGNORECASE)
    if not m:
        return sql
    n = int(m.group(1))
    cap = max(1, MAX_RESULT_ROWS - POST_PROCESS_APPEND_HEADROOM)
    if n <= cap:
        return sql
    semi = m.group(2) or ""
    new_tail = f"LIMIT {cap}{semi}"
    return text[: m.start()] + new_tail + text[m.end() :]


# ── Type aliases ──────────────────────────────────────────────────

Columns = list[str]
Rows = list[list[Any]]
StepConfig = dict[str, Any]


# ── Public entry point ────────────────────────────────────────────

def trim_detail_preserving_appended_tail(
    rows: Rows,
    sql_detail_row_count: int,
    max_total_rows: int,
) -> Rows:
    """
    When post-processing appended rows at the tail, the result can exceed ``max_total_rows``.
    Drop rows only from the **start** of the original SQL block so summary rows stay visible.

    ``sql_detail_row_count`` is the number of rows returned by the warehouse before any
    post-processing step ran (length of the initial row list passed into ``apply``).
    """
    if len(rows) <= max_total_rows or sql_detail_row_count <= 0:
        return rows
    excess = len(rows) - max_total_rows
    shave = min(excess, sql_detail_row_count)
    return rows[shave:sql_detail_row_count] + rows[sql_detail_row_count:]


def finalize_datamart_rows_after_post_process(
    rows: Rows,
    sql_detail_row_count: int,
) -> Rows:
    """Apply the datamart response row cap while keeping appended summary rows visible."""
    return trim_detail_preserving_appended_tail(
        rows, sql_detail_row_count, MAX_DATAMART_OUTPUT_ROWS
    )


def apply(
    columns: Columns,
    rows: Rows,
    config: list[StepConfig],
) -> tuple[Columns, Rows]:
    """
    Apply a sequence of post-processing steps to a SQL result set.

    Parameters
    ----------
    columns : list[str]   Column names from the SQL result.
    rows    : list[list]  Result rows (each row is a list of values).
    config  : list[dict]  Post-processing steps to apply in order.

    Returns
    -------
    (columns, rows) after all steps have been applied.

    Raises
    ------
    ValueError  If a step config is invalid or references a missing column.
    """
    if not config:
        return columns, rows

    # Work on copies so the originals are never mutated
    out_columns = list(columns)
    out_rows = [list(row) for row in rows]

    for i, step in enumerate(config):
        step_type = step.get("type", "")
        try:
            if step_type == "add_percentage_column":
                out_columns, out_rows = _add_percentage_column(out_columns, out_rows, step)
            elif step_type == "append_aggregate_row":
                out_columns, out_rows = _append_aggregate_row(out_columns, out_rows, step)
            elif step_type == "append_per_group_aggregate_rows":
                out_columns, out_rows = _append_per_group_aggregate_rows(
                    out_columns, out_rows, step
                )
            elif step_type == "add_derived_column":
                out_columns, out_rows = _add_derived_column(out_columns, out_rows, step)
            else:
                raise ValueError(f"Unknown post-processing step type: {step_type!r}")
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Step {i} ({step_type!r}) failed: {exc}") from exc

    return out_columns, out_rows


# ── Step implementations ──────────────────────────────────────────

def _col_index(columns: Columns, name: str) -> int:
    """
    Return the index of a column by name (case-insensitive fallback).
    LLM configs often mismatch warehouse alias casing.
    """
    if not name or not str(name).strip():
        raise ValueError("Column name is required")
    n = str(name).strip()
    if n in columns:
        return columns.index(n)
    n_lower = n.lower()
    matches = [i for i, c in enumerate(columns) if c.lower() == n_lower]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous column {name!r}; matches: {[columns[i] for i in matches]}"
        )
    raise ValueError(f"Column {name!r} not found. Available columns: {columns}")


def _group_equality(a: Any, b: Any) -> bool:
    """True if two group key cell values represent the same group (NaN-safe)."""
    if a is None and b is None:
        return True
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _group_identity_key(val: Any) -> tuple[Any, ...]:
    """Stable hashable key for set/dedupe (float NaN is not hashable as itself)."""
    if val is None:
        return (0, "none")
    if isinstance(val, float) and math.isnan(val):
        return (1, "nan")
    if isinstance(val, bool):
        return (2, val)
    if isinstance(val, int):
        return (3, val)
    if isinstance(val, float):
        return (4, val)
    return (5, str(val))


def _to_float(value: Any) -> float:
    """Safely convert a value to float, returning 0.0 for None/non-numeric."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# Labels often written into label_column on appended summary rows — exclude these
# rows from later aggregates so SUM/AVG stay over base data rows only.
_SUMMARY_LABEL_MARKERS: frozenset[str] = frozenset(
    {
        "total",
        "average",
        "avg",
        "mean",
        "summary",
        "subtotal",
        "grand total",
        "count",
        "minimum",
        "maximum",
        "min",
        "max",
        "sum",
    }
)


def _cell_matches_summary_marker(val: Any) -> bool:
    if isinstance(val, str):
        key = val.strip().lower()
        if key in _SUMMARY_LABEL_MARKERS:
            return True
    return False


def _data_rows_for_aggregations(
    columns: Columns,
    rows: Rows,
    label_column: str,
) -> Rows:
    """
    Rows to use when computing append_aggregate_row metrics.

    Prior summary rows (label column = Total / Average / …) are skipped so a new
    summary row does not average or sum older summary cells.
    """
    if not label_column:
        return rows
    try:
        li = _col_index(columns, label_column)
    except ValueError:
        return rows
    filtered = [row for row in rows if not _cell_matches_summary_marker(row[li])]
    return filtered if filtered else rows


def _add_percentage_column(
    columns: Columns,
    rows: Rows,
    step: StepConfig,
) -> tuple[Columns, Rows]:
    """
    Add a column showing each row's value as a percentage of the column total.

    Config keys:
        source_column (str, required) : existing column to compute % of
        new_column    (str, required) : name for the new % column
        decimal_places (int, default 2): rounding precision
    """
    source = step.get("source_column")
    new_col = step.get("new_column")
    decimals = int(step.get("decimal_places", 2))

    if not source or not new_col:
        raise ValueError("add_percentage_column requires 'source_column' and 'new_column'")

    src_idx = _col_index(columns, source)
    total = sum(_to_float(row[src_idx]) for row in rows)

    new_columns = columns + [new_col]
    new_rows = []
    for row in rows:
        val = _to_float(row[src_idx])
        pct = round((val / total * 100) if total != 0 else 0.0, decimals)
        new_rows.append(row + [pct])

    logger.debug("add_percentage_column: added %r (total=%s)", new_col, total)
    return new_columns, new_rows


def _append_aggregate_row(
    columns: Columns,
    rows: Rows,
    step: StepConfig,
) -> tuple[Columns, Rows]:
    """
    Append a single aggregate summary row at the bottom of the result.

    Config keys:
        aggregations  (dict, required) : {column_name: "SUM"|"AVG"|"MIN"|"MAX"|"COUNT"}
        label_column  (str, optional)  : column in which to place the label text
        label         (str, default "Summary") : text for the label cell
    """
    aggregations: dict[str, str] = step.get("aggregations", {})
    label_column: str = step.get("label_column", "")
    label: str = step.get("label", "Summary")

    if not aggregations:
        raise ValueError("append_aggregate_row requires 'aggregations' dict")

    agg_row: list[Any] = [None] * len(columns)

    # Place label
    if label_column:
        try:
            lix = _col_index(columns, label_column)
            agg_row[lix] = label
        except ValueError:
            pass

    data_rows = _data_rows_for_aggregations(columns, rows, label_column)

    for col_name, func_name in aggregations.items():
        try:
            idx = _col_index(columns, col_name)
        except ValueError:
            logger.warning("append_aggregate_row: column %r not found, skipping", col_name)
            continue
        values = [_to_float(row[idx]) for row in data_rows]
        func_upper = func_name.upper()

        if func_upper == "SUM":
            result = round(sum(values), 4)
        elif func_upper == "AVG":
            result = round(sum(values) / len(values), 4) if values else 0.0
        elif func_upper == "MIN":
            result = min(values) if values else 0.0
        elif func_upper == "MAX":
            result = max(values) if values else 0.0
        elif func_upper == "COUNT":
            result = len(values)
        else:
            raise ValueError(
                f"Unsupported aggregation function {func_name!r}. "
                "Use SUM, AVG, MIN, MAX, or COUNT."
            )

        agg_row[idx] = result

    new_rows = rows + [agg_row]
    logger.debug("append_aggregate_row: appended %r row", label)
    return columns, new_rows


def _append_per_group_aggregate_rows(
    columns: Columns,
    rows: Rows,
    step: StepConfig,
) -> tuple[Columns, Rows]:
    """
    Append one aggregate summary row per distinct ``group_column`` value.

    Config keys:
        group_column   (str, required) : column whose distinct values define groups
        aggregations   (dict, required): {column_name: "SUM"|"AVG"|...} per group
        label_column   (str, required) : column that receives the row label text
        label_format   (str, optional) : template with ``{group}`` replaced by the
                                         group value (default: "Average ({group})")
        aggregation_labels (dict, optional): {column_name: "display label"} for summary
                                         cards; when omitted, COUNT→"Count", AVG→"Average", etc.
    """
    group_column: str = step.get("group_column") or ""
    aggregations: dict[str, str] = step.get("aggregations") or {}
    label_column: str = step.get("label_column") or ""
    label_format: str = step.get("label_format") or "Average ({group})"

    if not group_column:
        raise ValueError(
            "append_per_group_aggregate_rows requires 'group_column' present in the result"
        )
    if not aggregations:
        raise ValueError("append_per_group_aggregate_rows requires 'aggregations' dict")
    if not label_column:
        raise ValueError(
            "append_per_group_aggregate_rows requires 'label_column' present in the result"
        )
    if "{group}" not in label_format:
        raise ValueError(
            "append_per_group_aggregate_rows: label_format must contain the placeholder {group}"
        )

    try:
        gidx = _col_index(columns, group_column)
        li = _col_index(columns, label_column)
    except ValueError as exc:
        raise ValueError(
            "append_per_group_aggregate_rows requires valid group_column and label_column "
            f"in the result ({exc})"
        ) from exc

    data_rows = _data_rows_for_aggregations(columns, rows, label_column)

    group_order_samples: list[tuple[tuple[Any, ...], Any]] = []
    seen_identity: set[tuple[Any, ...]] = set()
    for row in data_rows:
        raw_g = row[gidx]
        gid = _group_identity_key(raw_g)
        if gid in seen_identity:
            continue
        seen_identity.add(gid)
        group_order_samples.append((gid, raw_g))

    new_rows: Rows = [list(r) for r in rows]

    for _gid, sample_g in group_order_samples:
        subset = [r for r in data_rows if _group_equality(r[gidx], sample_g)]
        if not subset:
            continue

        label_text = label_format.replace("{group}", str(sample_g))
        agg_row: list[Any] = [None] * len(columns)
        agg_row[li] = label_text

        for col_name, func_name in aggregations.items():
            try:
                idx = _col_index(columns, col_name)
            except ValueError:
                logger.warning(
                    "append_per_group_aggregate_rows: column %r not found, skipping",
                    col_name,
                )
                continue
            values = [_to_float(row[idx]) for row in subset]
            func_upper = (func_name or "").upper()

            if func_upper == "SUM":
                result = round(sum(values), 4)
            elif func_upper == "AVG":
                result = round(sum(values) / len(values), 4) if values else 0.0
            elif func_upper == "MIN":
                result = min(values) if values else 0.0
            elif func_upper == "MAX":
                result = max(values) if values else 0.0
            elif func_upper == "COUNT":
                result = len(values)
            else:
                raise ValueError(
                    f"Unsupported aggregation function {func_name!r}. "
                    "Use SUM, AVG, MIN, MAX, or COUNT."
                )

            agg_row[idx] = result

        new_rows.append(agg_row)

    logger.debug(
        "append_per_group_aggregate_rows: appended %d group summary row(s)",
        len(group_order_samples),
    )
    return columns, new_rows


# ── Allowed identifiers for add_derived_column ────────────────────
# We evaluate expressions in a restricted namespace to prevent
# arbitrary code execution. Only safe builtins and the current row
# dict are available.

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "None": None,
    "True": True,
    "False": False,
}


def _add_derived_column(
    columns: Columns,
    rows: Rows,
    step: StepConfig,
) -> tuple[Columns, Rows]:
    """
    Add a new column computed from a Python expression evaluated per row.

    The expression has access to:
        row  : dict mapping column_name → value for the current row
        (plus safe builtins: abs, round, min, max, sum, len, str, int, float, bool)

    Config keys:
        new_column  (str, required) : name for the new column
        expression  (str, required) : Python expression string
                                      e.g. "round(row['salary'] / 12, 2)"

    Security: eval() is used with a restricted namespace. The expression
    must not contain import, exec, open, __builtins__, or attribute access
    on dunder names. These are blocked at the string level before eval.
    """
    new_col = step.get("new_column")
    expression = step.get("expression", "")

    if not new_col or not expression:
        raise ValueError("add_derived_column requires 'new_column' and 'expression'")

    # Basic security check — block dangerous patterns
    _assert_safe_expression(expression)

    new_columns = columns + [new_col]
    new_rows = []

    for row in rows:
        row_dict = dict(zip(columns, row))
        try:
            value = eval(  # noqa: S307 — restricted namespace, validated above
                expression,
                {"__builtins__": _SAFE_BUILTINS},
                {"row": row_dict},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "add_derived_column: expression %r failed for row: %s", expression, exc
            )
            value = None
        new_rows.append(row + [value])

    logger.debug("add_derived_column: added %r via expression %r", new_col, expression)
    return new_columns, new_rows


_BLOCKED_PATTERNS = (
    "import", "exec", "open", "__", "globals", "locals",
    "getattr", "setattr", "delattr", "compile", "eval",
)


def _assert_safe_expression(expression: str) -> None:
    """Raise ValueError if the expression contains dangerous patterns."""
    lower = expression.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in lower:
            raise ValueError(
                f"Expression contains disallowed pattern {pattern!r}. "
                "Only safe arithmetic and string operations are permitted."
            )
