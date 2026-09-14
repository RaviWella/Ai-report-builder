"""
Classify warehouse columns for SELECT projection vs join-only use.

Surrogate keys and foreign-key IDs should appear in JOIN / WHERE / GROUP BY when
needed, but not in the result grid unless the user explicitly asked for that identifier.
"""
from __future__ import annotations

import re
from typing import Optional

# SCD / ETL housekeeping — never user-facing in SELECT
_ALWAYS_JOIN_ONLY: frozenset[str] = frozenset(
    {
        "tenant_id",
        "is_current",
        "valid_from",
        "valid_to",
        "record_hash",
        "source_system",
        "row_hash",
        "scd_key",
        "effective_date_sk",
        "dbt_scd_id",
        "dbt_updated_at",
        "dbt_valid_from",
        "dbt_valid_to",
    }
)

_JOIN_ONLY_SUFFIXES: tuple[str, ...] = ("_sk",)

_SOURCE_ID_RE = re.compile(r"^source_.*_id$", re.IGNORECASE)

# FK column → display columns on the same table (if any exist, FK is join-only)
_DISPLAY_PAIR_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("employee_id", ("employee_no", "emp_fullname", "full_name", "employee_name", "emp_name")),
    ("designation_id", ("designation", "designation_name", "job_title", "title")),
    ("designation_sk", ("designation", "designation_name", "job_title", "title")),
    ("org_unit_id", ("org_unit_name", "branch", "organization_unit", "department")),
    ("org_unit_sk", ("org_unit_name", "branch", "organization_unit", "department")),
    ("leave_type_id", ("leave_type_name",)),
    ("payroll_group_id", ("payroll_group_name", "pay_group_name")),
    ("manager_employee_id", ("manager_name", "reporting_manager_name")),
    ("candidate_id", ("candidate_name", "full_name")),
    ("job_id", ("job_title", "position_title")),
    ("payroll_period_id", ("period_name", "pay_period", "payroll_period_name")),
    ("canonical_pay_item_id", ("pay_item_name", "canonical_pay_item_name")),
)


def is_join_only_column(column: str, table_columns: Optional[list[str]] = None) -> bool:
    """
    True when the column is a technical key — use in JOIN/WHERE, not in SELECT output.

    ``table_columns`` is the full column list for the same table (enables FK→name pairing).
    """
    col = (column or "").strip().lower()
    if not col:
        return False
    if col in _ALWAYS_JOIN_ONLY:
        return True
    if any(col.endswith(suffix) for suffix in _JOIN_ONLY_SUFFIXES):
        return True
    if _SOURCE_ID_RE.match(col):
        return True

    cols_lower = {c.lower() for c in (table_columns or [])}
    for fk, display_names in _DISPLAY_PAIR_RULES:
        if col == fk and any(d in cols_lower for d in display_names):
            return True

    if col.endswith("_id") and len(col) > 3:
        prefix = col[:-3]
        if f"{prefix}_name" in cols_lower or f"{prefix}_code" in cols_lower:
            return True

    return False


def partition_columns(columns: list[str]) -> tuple[list[str], list[str]]:
    """Split into (display_columns, join_only_columns) preserving input order."""
    display: list[str] = []
    join_only: list[str] = []
    for col in columns:
        if is_join_only_column(col, columns):
            join_only.append(col)
        else:
            display.append(col)
    return display, join_only


def join_only_columns_for_table(columns: list[str]) -> frozenset[str]:
    """Lowercase set of join-only column names for a table."""
    return frozenset(c.lower() for c in columns if is_join_only_column(c, columns))


def format_column_lists_for_prompt(
    display: list[str],
    join_only: list[str],
    *,
    max_display: int,
    max_join: int = 24,
) -> list[str]:
    """Lines for schema broker prompt (per table)."""
    lines: list[str] = []
    if display:
        shown = display[:max_display]
        col_list = ", ".join(shown)
        if len(display) > max_display:
            col_list += f", … (+{len(display) - max_display} more)"
        lines.append(f"  Columns (use in SELECT): {col_list}")
    if join_only:
        shown_j = join_only[:max_join]
        col_list = ", ".join(shown_j)
        if len(join_only) > max_join:
            col_list += f", … (+{len(join_only) - max_join} more)"
        lines.append(
            f"  Join keys (JOIN/WHERE/GROUP BY only — do NOT project in SELECT): {col_list}"
        )
    if not display and not join_only:
        lines.append("  Columns: (none)")
    return lines
