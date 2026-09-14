"""Deterministic SQL fixes after warehouse execution errors (before LLM retry)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from .sql_aliases import alias_to_table_short, schema_pattern_for_sql
from .sql_column_allowlist import resolve_column_for_table
from .sql_join_semantics import try_repair_join_semantics

if TYPE_CHECKING:
    from ..schema_broker import SchemaGrounding

# Columns on dim_leave_type (not fact_leave_transaction) per semantic_catalog.yaml
_DIM_LEAVE_COLUMNS = frozenset({"leave_type_name"})

# LLM shorthand -> physical column on fact_leave_transaction
_FACT_LEAVE_COLUMN_ALIASES: dict[str, str] = {
    "status": "leave_status_name",
    "approval_status": "leave_status_name",
    "leave_status": "leave_status_name",
    "final_status": "leave_final_status",
    "type": "leave_type_id",
    "leave_type": "leave_type_id",
}

# LLM often uses dim_* names on mart_employee_current (denormalized mart).
_MART_EMPLOYEE_COLUMN_ALIASES: dict[str, str] = {
    "designation_name": "designation",
    "job_title_name": "designation",
    "employee_name": "emp_fullname",
    "full_name": "emp_fullname",
    "name": "emp_fullname",
}


def _is_join_type_mismatch_error(error: str) -> bool:
    low = (error or "").lower()
    if "integer" not in low or "text" not in low:
        return False
    return "undefinedfunction" in low or "operator does not exist" in low


def try_repair_sql_execution_error(
    sql: str,
    error: str,
    grounding: Optional["SchemaGrounding"] = None,
) -> Optional[str]:
    """Return a repaired SQL string, or None if no rule applies."""
    if grounding is not None:
        semantic_fix = try_repair_join_semantics(sql, grounding)
        if semantic_fix and semantic_fix.strip() != sql.strip():
            return semantic_fix
    for repair in (
        repair_leave_duplicate_alias,
        repair_approver_join_keys,
        repair_integer_text_join_cast,
        repair_generic_join_cast_from_error,
        repair_leave_type_id_cast,
        lambda sql_in, err_in: repair_undefined_column(sql_in, err_in, grounding),
    ):
        fixed = repair(sql, error)
        if fixed and fixed.strip() != sql.strip():
            return fixed
    return None


def repair_leave_duplicate_alias(sql: str, error: str) -> Optional[str]:
    """
    Fix LLM reusing one alias (e.g. ``lt``) for both fact_leave_transaction and dim_leave_type,
    producing ``ON lt.leave_type_id = lt.leave_type_id``.
    """
    if "fact_leave_transaction" not in sql.lower() or "dim_leave_type" not in sql.lower():
        return None

    self_join = re.search(
        r"ON\s+(\w+)\.leave_type_id\s*=\s*\1\.leave_type_id",
        sql,
        flags=re.IGNORECASE,
    )
    dup_alias = re.search(
        r"fact_leave_transaction\s+(\w+).*?dim_leave_type\s+\1\b",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not self_join and not dup_alias:
        return None

    alias = (self_join or dup_alias).group(1)
    schema_pat = schema_pattern_for_sql()
    out = sql
    out = re.sub(
        rf"(\bJOIN\s+{schema_pat}\.fact_leave_transaction\s+){re.escape(alias)}\b",
        r"\1flt",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        rf"(\bJOIN\s+{schema_pat}\.dim_leave_type\s+){re.escape(alias)}\b",
        r"\1dlt",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        rf"\b{re.escape(alias)}\.leave_type_id\s*=\s*{re.escape(alias)}\.leave_type_id\b",
        "flt.leave_type_id::text = dlt.leave_type_id::text",
        out,
        flags=re.IGNORECASE,
    )
    for col in _DIM_LEAVE_COLUMNS:
        out = re.sub(
            rf"\b{re.escape(alias)}\.{col}\b",
            f"dlt.{col}",
            out,
            flags=re.IGNORECASE,
        )
    out = re.sub(rf"\b{re.escape(alias)}\.", "flt.", out, flags=re.IGNORECASE)
    return out


def repair_integer_text_join_cast(sql: str, error: str) -> Optional[str]:
    """Cast mixed integer/text join keys (designation_sk, shift_id, etc.)."""
    if not _is_join_type_mismatch_error(error):
        return None

    # Wrong join: business shift_id joined to surrogate shift_sk — use source_shift_id.
    shift_sk = re.search(
        r"(\w+)\.(shift_id|source_shift_id)\s*=\s*(\w+)\.shift_sk\b",
        sql,
        flags=re.IGNORECASE,
    )
    if shift_sk:
        left_alias, left_col, right_alias = shift_sk.groups()
        out = re.sub(
            rf"\b{re.escape(left_alias)}\.{re.escape(left_col)}\s*=\s*"
            rf"{re.escape(right_alias)}\.shift_sk\b",
            f"{right_alias}.source_shift_id::text = {left_alias}.{left_col.lower()}::text",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
        if out != sql:
            return out

    shift_sk_rev = re.search(
        r"(\w+)\.shift_sk\s*=\s*(\w+)\.(shift_id|source_shift_id)\b",
        sql,
        flags=re.IGNORECASE,
    )
    if shift_sk_rev:
        dim_alias, mart_alias, mart_col = shift_sk_rev.groups()
        out = re.sub(
            rf"\b{re.escape(dim_alias)}\.shift_sk\s*=\s*"
            rf"{re.escape(mart_alias)}\.{re.escape(mart_col)}\b",
            f"{dim_alias}.source_shift_id::text = {mart_alias}.{mart_col.lower()}::text",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
        if out != sql:
            return out

    patterns = [
        (
            r"(\w+)\.source_desig_id\s*=\s*(\w+)\.designation_sk\b",
            r"\1.source_desig_id = \2.source_desig_id",
        ),
        (
            r"(\w+)\.source_desig_id(?:\:\:text)?\s*=\s*(\w+)\.designation_sk(?:\:\:text)?\b",
            r"\1.source_desig_id = \2.source_desig_id",
        ),
        (
            r"(\w+)\.(shift_id|source_shift_id)\s*=\s*(\w+)\.(shift_id|source_shift_id|shift_sk)\b",
            r"\1.\2::text = \3.\4::text",
        ),
    ]
    out = sql
    for pat, repl in patterns:
        nxt = re.sub(pat, repl, out, count=1, flags=re.IGNORECASE)
        if nxt != out:
            return nxt
    return None


def repair_leave_type_id_cast(sql: str, error: str) -> Optional[str]:
    """Cast leave_type_id when Postgres reports integer = text on join."""
    if not _is_join_type_mismatch_error(error):
        return None
    if "leave_type_id" not in sql.lower():
        return None
    if "::text" in sql.lower():
        return None

    def _cast_join(m: re.Match[str]) -> str:
        left, right = m.group(1), m.group(2)
        if left == right:
            return m.group(0)
        return f"{left}.leave_type_id::text = {right}.leave_type_id::text"

    out = re.sub(
        r"(\w+)\.leave_type_id\s*=\s*(\w+)\.leave_type_id",
        _cast_join,
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    return out if out != sql else None


def repair_approver_join_keys(sql: str, error: str) -> Optional[str]:
    """
    Fix leave approver joins: source_approved_by / source_approver_emp_id are business ids,
    not employee_sk surrogates.
    """
    if not _is_join_type_mismatch_error(error) and "approved" not in error.lower():
        return None
    low_sql = sql.lower()
    if "approved" not in low_sql and "approver" not in low_sql:
        return None

    patterns = [
        (
            r"(\w+)\.employee_sk\s*=\s*(\w+)\.source_approved_by\b",
            r"\1.emp_no::text = \2.source_approved_by::text",
        ),
        (
            r"(\w+)\.employee_sk\s*=\s*(\w+)\.source_approver_emp_id\b",
            r"\1.emp_no::text = \2.source_approver_emp_id::text",
        ),
        (
            r"(\w+)\.source_approved_by\s*=\s*(\w+)\.employee_sk\b",
            r"\1.source_approved_by::text = \2.emp_no::text",
        ),
        (
            r"(\w+)\.source_approver_emp_id\s*=\s*(\w+)\.employee_sk\b",
            r"\1.source_approver_emp_id::text = \2.emp_no::text",
        ),
    ]
    out = sql
    for pat, repl in patterns:
        nxt = re.sub(pat, repl, out, count=1, flags=re.IGNORECASE)
        if nxt != out:
            return nxt
    return None


def repair_generic_join_cast_from_error(sql: str, error: str) -> Optional[str]:
    """Last-resort: cast both sides of the join predicate mentioned in the error."""
    if not _is_join_type_mismatch_error(error):
        return None
    m = re.search(
        r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)",
        error,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)",
            error,
            flags=re.IGNORECASE,
        )
    if not m:
        return None
    la, lc, ra, rc = m.groups()
    pat = (
        rf"\b{re.escape(la)}\.{re.escape(lc)}\s*=\s*"
        rf"{re.escape(ra)}\.{re.escape(rc)}\b"
    )
    repl = f"{la}.{lc}::text = {ra}.{rc}::text"
    out = re.sub(pat, repl, sql, count=1, flags=re.IGNORECASE)
    return out if out != sql else None


def repair_undefined_column(
    sql: str,
    error: str,
    grounding: Optional["SchemaGrounding"] = None,
) -> Optional[str]:
    """Fix common hallucinated column names (e.g. flt.status -> flt.leave_status_name)."""
    if "undefinedcolumn" not in error.lower() and "does not exist" not in error.lower():
        return None

    m = re.search(
        r'column\s+(\w+)\.(\w+)\s+does not exist',
        error,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"(\w+)\.(\w+)\s+does not exist",
            error,
            flags=re.IGNORECASE,
        )
    unqualified_col: Optional[str] = None
    if not m:
        um = re.search(
            r'column\s+"?(\w+)"?\s+does not exist',
            error,
            flags=re.IGNORECASE,
        )
        if um:
            unqualified_col = um.group(1).lower()

    if not m and not unqualified_col:
        return None

    if m:
        alias, bad_col = m.group(1).lower(), m.group(2).lower()
    else:
        alias, bad_col = "", unqualified_col or ""
    alias_map = alias_to_table_short(sql)
    table_short = alias_map.get(alias, "")

    replacement: Optional[str] = None
    if grounding and table_short:
        replacement = resolve_column_for_table(bad_col, table_short, grounding)
    elif grounding and not table_short:
        for short in {q.rsplit(".", 1)[-1] for q in grounding.qualified_tables}:
            replacement = resolve_column_for_table(bad_col, short, grounding)
            if replacement:
                table_short = short
                break

    if not replacement and table_short == "fact_leave_transaction":
        replacement = _FACT_LEAVE_COLUMN_ALIASES.get(bad_col)

    if not replacement and table_short == "mart_employee_current":
        replacement = _MART_EMPLOYEE_COLUMN_ALIASES.get(bad_col)

    if not replacement and "mart_employee_current" in sql.lower():
        replacement = _MART_EMPLOYEE_COLUMN_ALIASES.get(bad_col)

    if not replacement:
        return None

    if alias:
        pattern = rf"\b{re.escape(alias)}\.{re.escape(bad_col)}\b"
        out = re.sub(pattern, f"{alias}.{replacement}", sql, flags=re.IGNORECASE)
    else:
        pattern = rf"\b{re.escape(bad_col)}\b"
        out = re.sub(pattern, replacement, sql, count=0, flags=re.IGNORECASE)
    return out if out != sql else None


def try_repair_zero_row_sql(sql: str, analysis) -> Optional[str]:
    """Fix wrong WHERE literals or redundant filters on pre-filtered views."""
    from ..semantic.column_value_peek import ZeroRowFilterAnalysis

    if not isinstance(analysis, ZeroRowFilterAnalysis):
        return None

    original = sql
    out = repair_redundant_prefiltered_view_filters(sql) or sql

    for fl, vals in analysis.mismatches:
        fixed = repair_filter_literal_case(out, fl.column, fl.literal, vals)
        if fixed:
            out = fixed

    return out if out.strip() != original.strip() else None


def repair_redundant_prefiltered_view_filters(sql: str) -> Optional[str]:
    """Drop redundant status filters on views that already encode them."""
    if "vw_pending_leave_approvals" not in sql.lower():
        return None
    out = sql
    out = re.sub(
        r"\bWHERE\s+\w+\.(?:approval_status|leave_status)\s*=\s*'[^']*'\s*",
        "",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"\s+AND\s+\w+\.(?:approval_status|leave_status)\s*=\s*'[^']*'",
        "",
        out,
        flags=re.IGNORECASE,
    )
    return out if out != sql else None


def repair_filter_literal_case(
    sql: str,
    column: str,
    wrong_literal: str,
    actual_values: list[str],
) -> Optional[str]:
    """Replace a WHERE literal with the warehouse spelling when case differs."""
    if not actual_values:
        return None
    correct: Optional[str] = None
    for v in actual_values:
        if v.lower() == wrong_literal.lower():
            correct = v
            break
    if correct is None:
        for v in actual_values:
            if wrong_literal.lower() in v.lower() or v.lower() in wrong_literal.lower():
                correct = v
                break
    if correct is None or correct == wrong_literal:
        return None
    pat = (
        rf"((?:\w+\.)?{re.escape(column)}\s*=\s*)"
        rf"'{re.escape(wrong_literal)}'"
    )
    out = re.sub(pat, rf"\1'{correct}'", sql, count=1, flags=re.IGNORECASE)
    return out if out != sql else None

