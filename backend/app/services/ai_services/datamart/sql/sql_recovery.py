"""
Classify SQL / context failures and plan bounded recovery actions for the simple agent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..semantic.join_hints import related_table_short_names
from .sql_refs import warehouse_table_names_from_sql

# Bounded loop — expand context + regenerate until success or cap.
MAX_SQL_ATTEMPTS = 4


class SqlIssueKind(str, Enum):
    JOIN_TYPE_MISMATCH = "join_type_mismatch"
    MISSING_TABLE = "missing_table"
    MISSING_COLUMN = "missing_column"
    MAPPING_DRIFT = "mapping_drift"
    NO_SQL = "no_sql"
    LLM_ERROR = "llm_error"
    ZERO_ROWS_FILTER = "zero_rows_filter"
    UNKNOWN = "unknown"


class RecoveryActionKind(str, Enum):
    REPAIR_SQL = "repair_sql"
    EXPAND_CONTEXT = "expand_context"
    REGENERATE_SQL = "regenerate_sql"
    ABORT = "abort"


@dataclass
class SqlIssue:
    kind: SqlIssueKind
    message: str
    user_hint: str
    extra_tables: list[str] = field(default_factory=list)
    repairable: bool = False
    llm_guidance: str = ""


def llm_guidance_for_issue(kind: SqlIssueKind, error: str) -> str:
    low = (error or "").lower()
    if kind == SqlIssueKind.JOIN_TYPE_MISMATCH:
        if any(k in low for k in ("approved", "approver", "source_approved")):
            return (
                "Approver ids (source_approved_by, source_approver_emp_id) are business "
                "employee numbers — join hr.mart_employee_current ON "
                "mec.emp_no::text = fl.source_approver_emp_id::text, not employee_sk. "
                "For pending leave approvals prefer hr_semantic.vw_pending_leave_approvals."
            )
        return (
            "Fix join keys: do not join surrogate keys (_sk) to source/business ids. "
            "Use source_* columns or cast both sides ::text when types differ."
        )
    if kind == SqlIssueKind.MISSING_COLUMN:
        return "Use only columns listed in the schema blocks; do not invent names."
    if kind == SqlIssueKind.MISSING_TABLE:
        return "Use only tables from the schema blocks with correct schema prefix (hr / hr_semantic)."
    if kind == SqlIssueKind.MAPPING_DRIFT:
        return "Use source_* id columns from dim tables, not internal _sk keys unless both sides match."
    if kind == SqlIssueKind.NO_SQL:
        return "Return one complete SELECT with schema-qualified tables and LIMIT 500."
    if kind == SqlIssueKind.ZERO_ROWS_FILTER:
        return (
            "WHERE literal does not match stored values. Use Sample column values exactly, "
            "ILIKE when unsure, or omit filters on pre-filtered views like vw_pending_leave_approvals."
        )
    return "Fix only what failed; keep the same report intent and requested columns."


def diagnose_zero_row_filters(
    sql: str,
    *,
    error_message: str,
    llm_guidance: str,
) -> SqlIssue:
    return SqlIssue(
        kind=SqlIssueKind.ZERO_ROWS_FILTER,
        message=error_message[:500],
        user_hint="Query returned 0 rows — filter value may not exist in the column.",
        extra_tables=_tables_from_sql(sql),
        repairable=True,
        llm_guidance=llm_guidance,
    )


@dataclass
class RecoveryPlan:
    action: RecoveryActionKind
    issue: SqlIssue
    user_message: str
    detail: str


def diagnose_sql_failure(
    sql: Optional[str],
    error: str,
) -> SqlIssue:
    err = (error or "").strip()
    low = err.lower()

    if not sql and ("no sql" in low or "non_executable" in low):
        return SqlIssue(
            kind=SqlIssueKind.NO_SQL,
            message=err,
            user_hint="The model did not return runnable SQL.",
            repairable=False,
            llm_guidance=llm_guidance_for_issue(SqlIssueKind.NO_SQL, err),
        )

    if _is_join_type_mismatch(low):
        tables = _tables_from_sql(sql)
        if "shift" in low or "shift" in (sql or "").lower():
            tables.extend(["dim_shift", "mart_employee_current"])
        if any(k in low for k in ("approved", "approver", "leave")) or any(
            k in (sql or "").lower() for k in ("approved", "approver", "leave")
        ):
            tables.extend(
                [
                    "fact_leave_transaction",
                    "fact_leave_balance",
                    "vw_pending_leave_approvals",
                    "vw_leave_summary",
                    "mart_employee_current",
                ]
            )
        return SqlIssue(
            kind=SqlIssueKind.JOIN_TYPE_MISMATCH,
            message=err[:500],
            user_hint="Join keys use incompatible types (e.g. shift_sk vs shift_id, employee_sk vs emp_no).",
            extra_tables=list(dict.fromkeys(tables)),
            repairable=True,
            llm_guidance=llm_guidance_for_issue(SqlIssueKind.JOIN_TYPE_MISMATCH, err),
        )

    rel = re.search(r'relation "([^"]+)" does not exist', err, re.I)
    if rel or "undefinedtable" in low:
        short = rel.group(1).rsplit(".", 1)[-1] if rel else ""
        tables = _tables_from_sql(sql)
        if short:
            tables.append(short)
        return SqlIssue(
            kind=SqlIssueKind.MISSING_TABLE,
            message=err[:500],
            user_hint="SQL references a table that was not in context — loading more schema.",
            extra_tables=list(dict.fromkeys(tables)),
            repairable=False,
            llm_guidance=llm_guidance_for_issue(SqlIssueKind.MISSING_TABLE, err),
        )

    col = re.search(r'column\s+(\w+)\.(\w+)\s+does not exist', err, re.I)
    if col or "undefinedcolumn" in low:
        tables = _tables_from_sql(sql)
        alias, col_name = (col.group(1), col.group(2)) if col else ("", "")
        if "bank" in col_name.lower() or "bank" in low:
            tables.extend(
                ["fct_salary_bank_instruction", "dim_bank", "dim_bank_branch", "mart_employee_current"]
            )
        if "shift" in col_name.lower() or "shift" in low:
            tables.extend(["dim_shift", "mart_employee_current"])
        if "leave" in col_name.lower() or "leave" in low:
            tables.extend(
                [
                    "fact_leave_balance",
                    "fact_leave_transaction",
                    "vw_leave_summary",
                    "vw_pending_leave_approvals",
                    "dim_leave_type",
                ]
            )
        return SqlIssue(
            kind=SqlIssueKind.MISSING_COLUMN,
            message=err[:500],
            user_hint="SQL uses a column missing from context — expanding related tables.",
            extra_tables=list(dict.fromkeys(tables)),
            repairable=False,
            llm_guidance=llm_guidance_for_issue(SqlIssueKind.MISSING_COLUMN, err),
        )

    if "allowlist" in low or "not in the" in low and "column" in low:
        tables = _tables_from_sql(sql)
        tables.append("mart_employee_current")
        return SqlIssue(
            kind=SqlIssueKind.MAPPING_DRIFT,
            message=err[:500],
            user_hint="Column mapping mismatch — reloading schema for referenced tables.",
            extra_tables=list(dict.fromkeys(tables)),
            repairable=False,
            llm_guidance=llm_guidance_for_issue(SqlIssueKind.MAPPING_DRIFT, err),
        )

    if "llm" in low or "context length" in low or "timeout" in low:
        return SqlIssue(
            kind=SqlIssueKind.LLM_ERROR,
            message=err[:500],
            user_hint="AI model error — retrying with a smaller prompt.",
            repairable=False,
        )

    tables = _tables_from_sql(sql)
    return SqlIssue(
        kind=SqlIssueKind.UNKNOWN,
        message=err[:500],
        user_hint="Query failed — expanding schema and retrying.",
        extra_tables=tables,
        repairable=False,
        llm_guidance=llm_guidance_for_issue(SqlIssueKind.UNKNOWN, err),
    )


def _is_join_type_mismatch(low: str) -> bool:
    if "integer" not in low or "text" not in low:
        return False
    return "undefinedfunction" in low or "operator does not exist" in low


def plan_recovery(
    issue: SqlIssue,
    *,
    attempt: int,
    max_attempts: int = MAX_SQL_ATTEMPTS,
    repair_available: bool = False,
) -> RecoveryPlan:
    if attempt >= max_attempts:
        return RecoveryPlan(
            action=RecoveryActionKind.ABORT,
            issue=issue,
            user_message="Could not produce a working query after several attempts.",
            detail=f"max_attempts={max_attempts}",
        )

    if issue.kind == SqlIssueKind.NO_SQL:
        return RecoveryPlan(
            action=RecoveryActionKind.REGENERATE_SQL,
            issue=issue,
            user_message=f"Asking the model again ({attempt + 1}/{max_attempts})…",
            detail="no_sql_in_response",
        )

    if issue.kind == SqlIssueKind.ZERO_ROWS_FILTER:
        if issue.repairable and repair_available:
            return RecoveryPlan(
                action=RecoveryActionKind.REPAIR_SQL,
                issue=issue,
                user_message="Adjusting filter values to match warehouse data…",
                detail=issue.kind.value,
            )
        return RecoveryPlan(
            action=RecoveryActionKind.REGENERATE_SQL,
            issue=issue,
            user_message=f"Fixing filter values ({attempt + 1}/{max_attempts})…",
            detail=issue.kind.value,
        )

    if issue.repairable and repair_available:
        return RecoveryPlan(
            action=RecoveryActionKind.REPAIR_SQL,
            issue=issue,
            user_message="Fixing join keys automatically…",
            detail=issue.kind.value,
        )

    if issue.extra_tables:
        return RecoveryPlan(
            action=RecoveryActionKind.EXPAND_CONTEXT,
            issue=issue,
            user_message=(
                f"{issue.user_hint} (attempt {attempt + 1}/{max_attempts})"
            ),
            detail=f"expand_tables={','.join(issue.extra_tables[:6])}",
        )

    return RecoveryPlan(
        action=RecoveryActionKind.REGENERATE_SQL,
        issue=issue,
        user_message=f"Regenerating SQL ({attempt + 1}/{max_attempts})…",
        detail=issue.kind.value,
    )


def tables_for_recovery(issue: SqlIssue, sql: Optional[str]) -> list[str]:
    out = list(issue.extra_tables)
    out.extend(_tables_from_sql(sql))
    out.extend(related_table_short_names(out))
    return list(dict.fromkeys(t for t in out if t))


def _tables_from_sql(sql: Optional[str]) -> list[str]:
    if not sql:
        return []
    return list(warehouse_table_names_from_sql(sql))
