"""
Employee list with assigned shift name — mart_employee_current + dim_shift.

Avoids LLM NULL::text placeholders when shift dimension is in the warehouse.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from ..workspace.runtime_context import mart_schema_for_hints
from ..schema_broker import SchemaGrounding

_SHIFT_RE = re.compile(
    r"\b(?:shift|shifts|assigned\s+shift)\b",
    re.IGNORECASE,
)

_MART = "mart_employee_current"
_DIM_SHIFT = "dim_shift"

_NON_EMPLOYEE_DOMAIN_RE = re.compile(
    r"\b(?:leave|attendance|payroll|payslip|salary|overtime|benefit|"
    r"recruitment|recruit|hiring|candidate|candidates|applicant|pipeline|"
    r"linkedin|referral|requisition|attrition|turnover|time\s+off|vacation|"
    r"loan\s+deduction|epf|etf)\b",
    re.IGNORECASE,
)


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


def _pick_col(cols: list[str], candidates: tuple[str, ...]) -> Optional[str]:
    lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def _schema_for_short(grounding: SchemaGrounding, short: str) -> str:
    q = _qualified_for_short(grounding, short)
    if q and "." in q:
        return q.rsplit(".", 1)[0]
    return mart_schema_for_hints()


def _join_shift_via_dim_employee(
    grounding: SchemaGrounding,
    select_parts: list[str],
) -> str:
    """Fallback when mart lacks shift keys but dim_employee + dim_shift are grounded."""
    shorts = {s.lower() for s in grounding.table_short_names}
    if "dim_employee" not in shorts or _DIM_SHIFT not in shorts:
        return ""

    emp_cols = _cols_for_short(grounding, "dim_employee")
    shift_cols = _cols_for_short(grounding, _DIM_SHIFT)
    emp_no = _pick_col(emp_cols, ("emp_no", "employee_no"))
    emp_name = _pick_col(emp_cols, ("emp_fullname", "emp_name"))
    emp_shift = _pick_col(emp_cols, ("shift_id", "source_shift_id"))
    shift_name = _pick_col(shift_cols, ("shift_name", "name"))
    dim_shift_key = _pick_col(shift_cols, ("source_shift_id",))
    if not (emp_no and emp_name and emp_shift and shift_name and dim_shift_key):
        return ""

    emp_schema = _schema_for_short(grounding, "dim_employee")
    shift_schema = _schema_for_short(grounding, _DIM_SHIFT)
    select_parts[:] = [
        f"e.{emp_no} AS employee_no",
        f"e.{emp_name} AS employee_name",
        f"s.{shift_name} AS shift_name",
    ]
    join = (
        f"\nFROM {emp_schema}.dim_employee e\n"
        f"LEFT JOIN {shift_schema}.{_DIM_SHIFT} s\n"
        f"  ON s.{dim_shift_key}::text = e.{emp_shift}::text"
    )
    if "is_current" in {c.lower() for c in emp_cols}:
        join += "\nWHERE e.is_current IS TRUE"
    elif "is_current" in {c.lower() for c in shift_cols}:
        join += "\nWHERE s.is_current IS TRUE"
    return join


def looks_like_employee_shift_list(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
) -> bool:
    if not _SHIFT_RE.search(question or ""):
        return False
    q = (question or "").strip()
    if not q or not question_wants_row_detail(q):
        return False
    if _NON_EMPLOYEE_DOMAIN_RE.search(q):
        return False
    if not re.search(r"\b(?:employee|employees|staff|workforce|emp)\b", q, re.I):
        return False
    if grounding is None:
        return True
    shorts = {s.lower() for s in grounding.table_short_names}
    return _MART in shorts or "dim_employee" in shorts


def try_build_employee_shift_list_sql(
    question: str,
    *,
    grounding: SchemaGrounding,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    if not looks_like_employee_shift_list(question, grounding=grounding):
        return None

    mart_q = _qualified_for_short(grounding, _MART)
    mart_cols = _cols_for_short(grounding, _MART) if mart_q else []
    emp_no = _pick_col(mart_cols, ("emp_no", "employee_no"))
    emp_name = _pick_col(mart_cols, ("emp_fullname", "emp_name"))

    if not (emp_no and emp_name):
        join_sql = _join_shift_via_dim_employee(grounding, select_parts := [])
        if not join_sql:
            return None
        limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
        select_sql = ",\n    ".join(select_parts)
        emp_cols = _cols_for_short(grounding, "dim_employee")
        order_col = _pick_col(emp_cols, ("emp_fullname", "emp_name", "emp_no")) or "emp_fullname"
        return f"""SELECT
    {select_sql}{join_sql}
ORDER BY e.{order_col}
LIMIT {limit};"""

    schema = _schema_for_short(grounding, _MART)
    select_parts = [
        f"m.{emp_no} AS employee_no",
        f"m.{emp_name} AS employee_name",
    ]

    shift_on_mart = _pick_col(
        mart_cols,
        ("shift_name", "assigned_shift_name", "shift_description"),
    )
    join_sql = ""
    if shift_on_mart:
        select_parts.append(f"m.{shift_on_mart} AS shift_name")
    elif _DIM_SHIFT in {s.lower() for s in grounding.table_short_names}:
        shift_cols = _cols_for_short(grounding, _DIM_SHIFT)
        shift_name_col = _pick_col(shift_cols, ("shift_name", "name", "description"))
        dim_shift_key = _pick_col(shift_cols, ("source_shift_id",))
        mart_shift_keys = [
            c
            for c in (
                _pick_col(mart_cols, ("source_shift_id",)),
                _pick_col(mart_cols, ("shift_id",)),
            )
            if c
        ]
        if not (shift_name_col and dim_shift_key and mart_shift_keys):
            join_sql = _join_shift_via_dim_employee(grounding, select_parts)
            if not join_sql:
                return None
        else:
            shift_schema = _schema_for_short(grounding, _DIM_SHIFT)
            select_parts.append(f"ds.{shift_name_col} AS shift_name")
            mart_shift_key = mart_shift_keys[0]
            join_sql = (
                f"\nLEFT JOIN {shift_schema}.{_DIM_SHIFT} ds\n"
                f"  ON ds.{dim_shift_key}::text = m.{mart_shift_key}::text"
            )
            if "is_current" in {c.lower() for c in shift_cols}:
                join_sql += "\n AND ds.is_current IS TRUE"
    else:
        return None

    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    where_clause = ""
    if join_sql.startswith("\nFROM "):
        # dim_employee fallback embeds FROM/WHERE in join_sql
        body = join_sql
        join_sql = ""
    else:
        body = ""
        if "is_current" in {c.lower() for c in mart_cols}:
            where_clause = "\nWHERE m.is_current IS TRUE"

    order_col = emp_name
    select_sql = ",\n    ".join(select_parts)
    if body:
        return f"""SELECT
    {select_sql}{body}
ORDER BY e.{order_col}
LIMIT {limit};"""
    return f"""SELECT
    {select_sql}
FROM {schema}.{_MART} m{join_sql}{where_clause}
ORDER BY m.{order_col}
LIMIT {limit};"""
