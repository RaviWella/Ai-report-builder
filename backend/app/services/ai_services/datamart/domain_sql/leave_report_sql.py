"""
Deterministic leave + employee detail SQL grounded on the broker allowlist.

Builds SQL only from tables/columns present in SchemaGrounding so binding cannot fail
on invented mart/view columns.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from ..workspace.runtime_context import mart_schema_for_hints
from ..schema_broker import SchemaGrounding

_LEAVE_DOMAIN_RE = re.compile(
    r"\b(?:leave|time\s+off|vacation|annual\s+leave|sick\s+leave)\b",
    re.IGNORECASE,
)

_EMP_TABLE_CANDIDATES = (
    "mart_employee_current",
    "dim_employee",
    "snap_employee",
)

_LEAVE_FACT_PRIORITY = (
    "fact_leave_transaction",
    "fact_leave_balance",
    "vw_leave_summary",
)


def looks_like_leave_detail_report(question: str) -> bool:
    q = (question or "").strip()
    if not q or not _LEAVE_DOMAIN_RE.search(q):
        return False
    if not question_wants_row_detail(q):
        return False
    if re.search(
        r"\bleave\s+(?:transaction|type|start|end|status|days|request|balance)\b",
        q,
        re.I,
    ):
        return True
    if re.search(r"\bcombining\b.*\bleave\b|\bleave\b.*\bcombining\b", q, re.I):
        return True
    if re.search(r"\bapproved\s+leave\b|\bleave\s+requests?\b", q, re.I):
        return True
    if re.search(r"\binclude\b.*\bleave\b", q, re.I):
        return True
    return False


def _schema_from_grounding(grounding: SchemaGrounding) -> str:
    for qualified in grounding.qualified_tables:
        if "." in qualified:
            return qualified.rsplit(".", 1)[0]
    return mart_schema_for_hints()


def _grounded_shorts(grounding: SchemaGrounding) -> set[str]:
    return {s.lower() for s in grounding.table_short_names}


def _qualified_for_short(grounding: SchemaGrounding, short: str) -> Optional[str]:
    low = short.lower()
    for q in grounding.qualified_tables:
        if q.rsplit(".", 1)[-1].lower() == low:
            return q
    return None


def _cols_for_short(grounding: SchemaGrounding, short: str) -> list[str]:
    q = _qualified_for_short(grounding, short)
    if not q:
        return []
    return list(grounding.columns_by_table.get(q) or [])


def _pick_col(columns: list[str], candidates: tuple[str, ...]) -> Optional[str]:
    by_low = {c.lower(): c for c in columns}
    for name in candidates:
        if name.lower() in by_low:
            return by_low[name.lower()]
    return None


def _employee_table_score(cols: list[str]) -> int:
    score = 0
    if _pick_col(cols, ("emp_fullname", "full_name", "employee_name", "emp_name")):
        score += 3
    if _pick_col(cols, ("employee_no", "emp_no", "employee_id")):
        score += 2
    if _pick_col(cols, ("branch_name", "location_name", "branch", "designation_department")):
        score += 1
    return score


def _pick_employee_table(grounding: SchemaGrounding) -> Optional[str]:
    have = _grounded_shorts(grounding)
    best: Optional[str] = None
    best_score = -1
    for short in _EMP_TABLE_CANDIDATES:
        if short not in have:
            continue
        score = _employee_table_score(_cols_for_short(grounding, short))
        if score > best_score:
            best_score = score
            best = short
    return best


def _pick_leave_table(grounding: SchemaGrounding) -> Optional[str]:
    have = _grounded_shorts(grounding)
    if "fact_leave_transaction" in have and "dim_leave_type" in have:
        return "fact_leave_transaction"
    for t in _LEAVE_FACT_PRIORITY:
        if t in have:
            return t
    return None


def _join_condition(
    emp_alias: str,
    emp_cols: list[str],
    leave_alias: str,
    leave_cols: list[str],
) -> Optional[str]:
    pairs = (
        ("employee_id", "source_emp_id"),
        ("employee_id", "employee_id"),
        ("employee_sk", "employee_sk"),
        ("employee_no", "source_emp_id"),
        ("emp_no", "source_emp_id"),
        ("employee_sk", "employee_id"),
        ("employee_id", "employee_sk"),
        ("emp_no", "employee_sk"),
    )
    for left, right in pairs:
        lc = _pick_col(emp_cols, (left,))
        rc = _pick_col(leave_cols, (right,))
        if lc and rc:
            return f"{emp_alias}.{lc}::text = {leave_alias}.{rc}::text"
    return None


def build_leave_sql_from_grounding(
    question: str,
    grounding: SchemaGrounding,
    *,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    """Build leave detail SQL using only allowlisted tables and columns."""
    if not grounding.columns_by_table:
        return None

    emp_short = _pick_employee_table(grounding)
    leave_short = _pick_leave_table(grounding)
    if not emp_short or not leave_short:
        return None

    schema = _schema_from_grounding(grounding)
    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    emp_cols = _cols_for_short(grounding, emp_short)
    leave_cols = _cols_for_short(grounding, leave_short)
    emp_alias = "e"
    leave_alias = "flt" if leave_short == "fact_leave_transaction" else "flb"
    if leave_short == "vw_leave_summary":
        leave_alias = "v"

    join_on = _join_condition(emp_alias, emp_cols, leave_alias, leave_cols)
    if not join_on:
        return None

    select_parts: list[str] = []
    name_col = _pick_col(
        emp_cols,
        ("full_name", "emp_fullname", "employee_name", "emp_name"),
    )
    if name_col:
        select_parts.append(f"    {emp_alias}.{name_col} AS employee_name")
    id_col = _pick_col(emp_cols, ("employee_no", "emp_no", "employee_id"))
    if id_col:
        select_parts.append(f"    {emp_alias}.{id_col} AS employee_id")
    branch_col = _pick_col(
        emp_cols,
        ("branch_name", "location_name", "branch", "designation_department"),
    )
    if branch_col:
        select_parts.append(f"    {emp_alias}.{branch_col} AS branch")

    if leave_short == "fact_leave_transaction" and "dim_leave_type" in _grounded_shorts(
        grounding
    ):
        dlt_cols = _cols_for_short(grounding, "dim_leave_type")
        type_col = _pick_col(dlt_cols, ("leave_type_name", "leave_type"))
        if type_col:
            select_parts.append(f"    dlt.{type_col} AS leave_type")
        for label, candidates in (
            ("leave_start_date", ("leave_start_date", "leave_start")),
            ("leave_end_date", ("leave_end_date", "leave_end")),
            ("total_leave_days", ("leave_days", "days_approved", "total_leave_days")),
            ("leave_status", ("leave_status_name", "leave_status")),
        ):
            c = _pick_col(leave_cols, candidates)
            if c:
                select_parts.append(f"    {leave_alias}.{c} AS {label}")
    else:
        type_col = _pick_col(leave_cols, ("leave_type_name", "leave_type_code"))
        if type_col:
            select_parts.append(f"    {leave_alias}.{type_col} AS leave_type")
        start_col = _pick_col(
            leave_cols,
            ("leave_start_date", "period_label", "leave_start"),
        )
        if start_col:
            select_parts.append(f"    {leave_alias}.{start_col} AS leave_start_date")
        end_col = _pick_col(
            leave_cols,
            ("leave_end_date", "period_label", "leave_end"),
        )
        if end_col:
            select_parts.append(f"    {leave_alias}.{end_col} AS leave_end_date")
        days_col = _pick_col(
            leave_cols,
            ("leave_days", "days_approved", "days_taken", "total_leave_days"),
        )
        if days_col:
            select_parts.append(f"    {leave_alias}.{days_col} AS total_leave_days")
        status_col = _pick_col(leave_cols, ("leave_status_name", "leave_status"))
        if status_col:
            select_parts.append(f"    {leave_alias}.{status_col} AS leave_status")
        elif re.search(r"\bapproved\b", question, re.I):
            select_parts.append("    'approved' AS leave_status")

    if len(select_parts) < 3:
        return None

    q = question.lower()
    approved_filter = ""
    if re.search(r"\bapproved\b", q) or re.search(r"\bapproval\b", q):
        status_c = _pick_col(leave_cols, ("leave_status_name", "leave_status"))
        days_c = _pick_col(leave_cols, ("days_approved", "days_taken", "leave_days"))
        if status_c:
            approved_filter = (
                f"\n  AND {leave_alias}.{status_c} ILIKE '%approved%'"
            )
        elif days_c:
            approved_filter = f"\n  AND {leave_alias}.{days_c} > 0"

    is_current = _pick_col(emp_cols, ("is_current",))
    is_current_clause = f"\n   AND {emp_alias}.{is_current} IS TRUE" if is_current else ""

    from_clause = (
        f"FROM {schema}.{emp_short} {emp_alias}\n"
        f"INNER JOIN {schema}.{leave_short} {leave_alias}\n"
        f"    ON {join_on}{is_current_clause}"
    )
    if leave_short == "fact_leave_transaction" and "dim_leave_type" in _grounded_shorts(
        grounding
    ):
        dlt_cols = _cols_for_short(grounding, "dim_leave_type")
        lt_id_leave = _pick_col(leave_cols, ("leave_type_id",))
        lt_id_dim = _pick_col(dlt_cols, ("leave_type_id",))
        if lt_id_leave and lt_id_dim:
            from_clause += (
                f"\nINNER JOIN {schema}.dim_leave_type dlt\n"
                f"    ON {leave_alias}.{lt_id_leave}::text = dlt.{lt_id_dim}::text"
            )

    order_bits: list[str] = []
    leave_order = _pick_col(
        leave_cols,
        ("leave_start_date", "period_label", "leave_start"),
    )
    if leave_order:
        order_bits.append(f"{leave_alias}.{leave_order} DESC NULLS LAST")
    if name_col:
        order_bits.append(f"{emp_alias}.{name_col}")
    order_sql = f"ORDER BY {', '.join(order_bits)}" if order_bits else ""

    select_sql = ",\n".join(select_parts)
    where_name = f"{emp_alias}.{name_col} IS NOT NULL" if name_col else "1=1"

    return f"""SELECT
{select_sql}
{from_clause}
WHERE {where_name}{approved_filter}
{order_sql}
LIMIT {limit};"""


def try_build_leave_detail_report_sql(
    question: str,
    *,
    grounded_short_names: Optional[list[str]] = None,
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[str]:
    if not looks_like_leave_detail_report(question):
        return None
    if grounding and grounding.columns_by_table:
        built = build_leave_sql_from_grounding(question, grounding)
        if built:
            return built
    return None
