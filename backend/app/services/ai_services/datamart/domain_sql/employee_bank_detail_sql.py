"""
Deterministic employee + bank detail SQL from the grounded allowlist.

Used when the LLM returns SQL:NONE or refuses a multi-column employee/bank list
despite mart_employee_current and bank tables being grounded.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from ..workspace.runtime_context import mart_schema_for_hints
from ..schema_broker import SchemaGrounding

_EMPLOYEE_BANK_RE = re.compile(
    r"\b(?:bank|bank\s+details?|account)\b",
    re.IGNORECASE,
)
_EMPLOYEE_LIST_RE = re.compile(
    r"\b(?:employee|employees|staff|workforce)\b",
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


def _join_bank_via_fact_or_dim(
    *,
    grounding: SchemaGrounding,
    mart_alias: str,
    join_key: str,
    select_parts: list[str],
) -> str:
    """
    Build JOIN clause for bank columns via salary bank fact + dim_bank, or
    dim_employee when the fact table is missing from grounding.
    """
    shorts = {s.lower() for s in grounding.table_short_names}
    bank_fact = "bi"
    dim_bank_alias = "dbk"

    bank_short = None
    for cand in ("fct_salary_bank_instruction", "fact_salary_bank_instruction"):
        if cand in shorts:
            bank_short = cand
            break

    if bank_short:
        bank_schema = _schema_for_short(grounding, bank_short)
        bank_cols = _cols_for_short(grounding, bank_short)
        bank_name_col = _pick_col(bank_cols, ("bank_passbook_name", "account_number"))
        bank_key_fact = _pick_col(
            bank_cols, ("employee_sk", "employee_id", "source_emp_id")
        )
        bank_src_bank = _pick_col(bank_cols, ("source_bank_id", "bank_id"))
        account_col = _pick_col(bank_cols, ("account_number",))

        dim_short = "dim_bank" if "dim_bank" in shorts else None
        if dim_short and bank_src_bank:
            dim_schema = _schema_for_short(grounding, dim_short)
            dim_cols = _cols_for_short(grounding, dim_short)
            bank_name_dim = _pick_col(dim_cols, ("bank_name",))
            bank_code_dim = _pick_col(dim_cols, ("bank_code", "code"))
            bank_sk_dim = _pick_col(dim_cols, ("bank_sk", "source_bank_id", "bank_id"))
            if bank_name_dim and bank_sk_dim and bank_key_fact:
                if bank_code_dim:
                    select_parts.append(f"{dim_bank_alias}.{bank_code_dim} AS bank_code")
                select_parts.append(f"{dim_bank_alias}.{bank_name_dim} AS bank_name")
                if account_col:
                    select_parts.append(f"{bank_fact}.{account_col} AS account_number")
                return (
                    f"\nLEFT JOIN {bank_schema}.{bank_short} {bank_fact}\n"
                    f"  ON {bank_fact}.{bank_key_fact} = {mart_alias}.{join_key}\n"
                    f"LEFT JOIN {dim_schema}.{dim_short} {dim_bank_alias}\n"
                    f"  ON {dim_bank_alias}.{bank_sk_dim}::text = "
                    f"{bank_fact}.{bank_src_bank}::text"
                )
        if bank_name_col and bank_key_fact:
            select_parts.append(f"{bank_fact}.{bank_name_col} AS bank_name")
            if account_col:
                select_parts.append(f"{bank_fact}.{account_col} AS account_number")
            return (
                f"\nLEFT JOIN {bank_schema}.{bank_short} {bank_fact}\n"
                f"  ON {bank_fact}.{bank_key_fact} = {mart_alias}.{join_key}"
            )

    # Fallback: bank labels on dim_employee when salary bank fact is not grounded.
    if "dim_employee" in shorts:
        dim_schema = _schema_for_short(grounding, "dim_employee")
        dim_cols = _cols_for_short(grounding, "dim_employee")
        dim_key = _pick_col(dim_cols, ("employee_sk", "employee_id"))
        bank_name = _pick_col(dim_cols, ("bank_name",))
        branch_name = _pick_col(dim_cols, ("branch_name", "bank_branch_name"))
        account = _pick_col(
            dim_cols, ("account_number", "bank_account_number", "bank_account_no")
        )
        if dim_key and (bank_name or branch_name or account):
            if bank_name:
                select_parts.append(f"de.{bank_name} AS bank_name")
            if branch_name:
                select_parts.append(f"de.{branch_name} AS bank_branch_name")
            if account:
                select_parts.append(f"de.{account} AS account_number")
            return (
                f"\nLEFT JOIN {dim_schema}.dim_employee de\n"
                f"  ON de.{dim_key} = {mart_alias}.{join_key}"
            )

    return ""


def _schema_for_short(grounding: SchemaGrounding, short: str) -> str:
    q = _qualified_for_short(grounding, short)
    if q and "." in q:
        return q.rsplit(".", 1)[0]
    return mart_schema_for_hints()


def looks_like_employee_bank_detail_report(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
) -> bool:
    q = (question or "").strip()
    if not q or not question_wants_row_detail(q):
        return False
    if not _EMPLOYEE_BANK_RE.search(q) or not _EMPLOYEE_LIST_RE.search(q):
        return False
    if grounding and "mart_employee_current" not in {
        s.lower() for s in grounding.table_short_names
    }:
        return False
    return True


def try_build_employee_bank_detail_sql(
    question: str,
    *,
    grounding: SchemaGrounding,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    """Build SQL only from columns present on grounded tables."""
    if not looks_like_employee_bank_detail_report(question, grounding=grounding):
        return None

    mart = "mart_employee_current"
    if mart not in {s.lower() for s in grounding.table_short_names}:
        return None

    mart_schema = _schema_for_short(grounding, mart)
    mart_cols = _cols_for_short(grounding, mart)
    emp_no = _pick_col(mart_cols, ("emp_no", "employee_no"))
    emp_name = _pick_col(mart_cols, ("emp_fullname", "emp_name", "full_name"))
    emp_cat = _pick_col(mart_cols, ("employee_category", "employment_type"))
    emp_sk = _pick_col(mart_cols, ("employee_sk",))

    if not emp_no or not emp_name:
        return None

    select_parts = [
        f"m.{emp_no} AS employee_number",
        f"m.{emp_name} AS employee_full_name",
    ]
    if emp_cat:
        select_parts.append(f"m.{emp_cat} AS employment_category")

    join_key = emp_sk or _pick_col(mart_cols, ("employee_sk", "employee_id"))
    if not join_key:
        return None

    join_bank = _join_bank_via_fact_or_dim(
        grounding=grounding,
        mart_alias="m",
        join_key=join_key,
        select_parts=select_parts,
    )
    if not join_bank:
        return None

    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    select_sql = ",\n    ".join(select_parts)
    where_clause = ""
    if "is_current" in {c.lower() for c in mart_cols}:
        where_clause = "\nWHERE m.is_current IS TRUE"
    return f"""SELECT
    {select_sql}
FROM {mart_schema}.{mart} m{join_bank}{where_clause}
ORDER BY m.{emp_name}
LIMIT {limit};"""
