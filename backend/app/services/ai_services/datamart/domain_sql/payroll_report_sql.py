"""
Deterministic payroll summary SQL grounded on the broker allowlist.

Prefers hr_semantic.vw_payroll_summary when present; otherwise mart_employee_current
joined to dim_payroll_group for group frequency and currency.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from ..workspace.runtime_context import mart_schema_for_hints
from ..schema_broker import SchemaGrounding

_PAYROLL_DOMAIN_RE = re.compile(
    r"\b(?:payroll|payslip|pay\s+summary|salary\s+summary)\b",
    re.IGNORECASE,
)

_EMP_TABLE_CANDIDATES = (
    "mart_employee_current",
    "dim_employee",
    "snap_employee",
)

_PAYROLL_VIEW_PRIORITY = (
    "vw_payroll_summary",
    "mart_processed_payroll_summary",
)

_PAYROLL_FACT_PRIORITY = (
    "fact_payroll",
    "fct_processed_salary",
)


def looks_like_payroll_detail_report(question: str) -> bool:
    q = (question or "").strip()
    if not q or not _PAYROLL_DOMAIN_RE.search(q):
        return False
    if re.search(
        r"\bpayroll\s+summary\b|\bcombining\b.*\bpayroll\b|\bpayroll\b.*\bcombining\b",
        q,
        re.I,
    ):
        return True
    if re.search(
        r"\bpayroll\s+group\b|\bpay\s+frequency\b|\bcurrency\b|\bbasic\s+salary\b",
        q,
        re.I,
    ) and question_wants_row_detail(q):
        return True
    if question_wants_row_detail(q) and re.search(r"\binclude\b", q, re.I):
        return True
    return False


def _schema_from_grounding(grounding: SchemaGrounding) -> str:
    for qualified in grounding.qualified_tables:
        if "." in qualified:
            return qualified.rsplit(".", 1)[0]
    return mart_schema_for_hints()


def _schema_for_short(grounding: SchemaGrounding, short: str) -> str:
    q = _qualified_for_short(grounding, short)
    if q and "." in q:
        return q.rsplit(".", 1)[0]
    return _schema_from_grounding(grounding)


def _grounded_shorts(grounding: SchemaGrounding) -> set[str]:
    return {s.lower() for s in grounding.table_short_names}


def _qualified_for_short(grounding: SchemaGrounding, short: str) -> Optional[str]:
    low = short.lower()
    matches = [q for q in grounding.qualified_tables if q.rsplit(".", 1)[-1].lower() == low]
    if not matches:
        return None
    if low.startswith("vw_"):
        for q in matches:
            if q.lower().startswith("hr_semantic."):
                return q
        from ..workspace.runtime_context import get_datamart_context

        ctx = get_datamart_context()
        if ctx is not None:
            prefer = f"{ctx.primary_schema}.{short}".lower()
            for q in matches:
                if q.lower() == prefer:
                    return q
    return matches[0]


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
    if _pick_col(cols, ("basic_salary",)):
        score += 2
    if _pick_col(cols, ("payroll_group", "payroll_group_name")):
        score += 1
    if _pick_col(cols, ("branch_name", "location_name", "branch")):
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


def _pick_payroll_view(grounding: SchemaGrounding) -> Optional[str]:
    have = _grounded_shorts(grounding)
    for t in _PAYROLL_VIEW_PRIORITY:
        if t in have:
            cols = _cols_for_short(grounding, t)
            if _pick_col(
                cols,
                ("emp_fullname", "employee_id", "payroll_group_name", "basic_salary"),
            ):
                return t
    return None


def _join_payroll_group_on(
    left_alias: str,
    left_cols: list[str],
    pg_alias: str,
    pg_cols: list[str],
) -> Optional[str]:
    pairs = (
        ("payroll_group_name", "payroll_group_name"),
        ("payroll_group", "payroll_group_name"),
        ("payroll_group", "source_payroll_group_id"),
        ("payroll_group_sk", "payroll_group_sk"),
        ("source_payroll_group_id", "source_payroll_group_id"),
    )
    for left, right in pairs:
        lc = _pick_col(left_cols, (left,))
        rc = _pick_col(pg_cols, (right,))
        if lc and rc:
            return f"{left_alias}.{lc}::text = {pg_alias}.{rc}::text"
    return None


def _join_employee_to_fact(
    emp_alias: str,
    emp_cols: list[str],
    fact_alias: str,
    fact_cols: list[str],
) -> Optional[str]:
    pairs = (
        ("employee_id", "employee_id"),
        ("employee_sk", "employee_sk"),
        ("emp_no", "employee_id"),
        ("employee_no", "employee_id"),
        ("source_emp_id", "employee_id"),
        ("employee_sk", "employee_sk"),
    )
    for left, right in pairs:
        lc = _pick_col(emp_cols, (left,))
        rc = _pick_col(fact_cols, (right,))
        if lc and rc:
            return f"{emp_alias}.{lc}::text = {fact_alias}.{rc}::text"
    return None


def _append_payroll_group_select(
    select_parts: list[str],
    pg_alias: str,
    pg_cols: list[str],
) -> None:
    pg_name = _pick_col(pg_cols, ("payroll_group_name",))
    if pg_name:
        select_parts.append(f"    {pg_alias}.{pg_name} AS payroll_group_name")
    freq = _pick_col(pg_cols, ("payroll_frequency",))
    if freq:
        select_parts.append(f"    {pg_alias}.{freq} AS pay_frequency")
    curr = _pick_col(pg_cols, ("currency_code",))
    if curr:
        select_parts.append(f"    {pg_alias}.{curr} AS currency_code")


def _select_parts_from_payroll_view(
    view_cols: list[str],
    *,
    view_alias: str,
) -> tuple[list[str], Optional[str], Optional[str], Optional[str]]:
    """
    Return (select_parts, name_col, payroll_group_col, branch_col) for vw_payroll_summary.

    Note: the semantic view may not expose dim_employee.full_name; prefer view-native fields.
    """
    select_parts: list[str] = []
    name_col = _pick_col(view_cols, ("emp_fullname", "employee_name", "emp_name"))
    if name_col:
        select_parts.append(f"    {view_alias}.{name_col} AS employee_name")
    id_col = _pick_col(view_cols, ("employee_id", "emp_no", "employee_no"))
    if id_col:
        select_parts.append(f"    {view_alias}.{id_col} AS employee_id")
    pg_on_view = _pick_col(view_cols, ("payroll_group_name", "payroll_group"))
    if pg_on_view:
        select_parts.append(f"    {view_alias}.{pg_on_view} AS payroll_group_name")
    freq_col = _pick_col(view_cols, ("payroll_frequency", "pay_frequency"))
    if freq_col:
        select_parts.append(f"    {view_alias}.{freq_col} AS pay_frequency")
    curr_col = _pick_col(view_cols, ("currency_code",))
    if curr_col:
        select_parts.append(f"    {view_alias}.{curr_col} AS currency_code")
    branch_col = _pick_col(view_cols, ("branch", "branch_name", "location_name"))
    if branch_col:
        select_parts.append(f"    {view_alias}.{branch_col} AS branch")
    sal_col = _pick_col(view_cols, ("basic_salary", "gross_salary"))
    if sal_col:
        select_parts.append(f"    {view_alias}.{sal_col} AS basic_salary")
    return select_parts, name_col, pg_on_view, branch_col


def _maybe_join_dim_payroll_group(
    *,
    grounding: SchemaGrounding,
    left_alias: str,
    left_cols: list[str],
    pg_on_view: Optional[str],
    select_parts: list[str],
    from_clause: str,
) -> str:
    have = _grounded_shorts(grounding)
    if "dim_payroll_group" not in have:
        return from_clause
    pg_cols = _cols_for_short(grounding, "dim_payroll_group")
    pg_schema = _schema_for_short(grounding, "dim_payroll_group")
    pg_alias = "pg"
    join_on = _join_payroll_group_on(left_alias, left_cols, pg_alias, pg_cols)
    if join_on:
        from_clause += (
            f"\nLEFT JOIN {pg_schema}.dim_payroll_group {pg_alias}\n"
            f"    ON {join_on}"
        )
        _append_payroll_group_select(select_parts, pg_alias, pg_cols)
        return from_clause
    if pg_on_view:
        freq = _pick_col(left_cols, ("payroll_frequency",))
        if freq:
            select_parts.append(f"    {left_alias}.{freq} AS pay_frequency")
        curr = _pick_col(left_cols, ("currency_code",))
        if curr:
            select_parts.append(f"    {left_alias}.{curr} AS currency_code")
    return from_clause


def _build_from_vw_payroll_summary(
    question: str,
    grounding: SchemaGrounding,
    view_short: str,
    *,
    max_rows: int,
) -> Optional[str]:
    view_cols = _cols_for_short(grounding, view_short)
    view_schema = _schema_for_short(grounding, view_short)
    v_alias = "v"
    select_parts, name_col, pg_on_view, _branch_col = _select_parts_from_payroll_view(
        view_cols,
        view_alias=v_alias,
    )
    from_clause = f"FROM {view_schema}.{view_short} {v_alias}"
    from_clause = _maybe_join_dim_payroll_group(
        grounding=grounding,
        left_alias=v_alias,
        left_cols=view_cols,
        pg_on_view=pg_on_view,
        select_parts=select_parts,
        from_clause=from_clause,
    )

    if len(select_parts) < 4:
        return None

    order_bits: list[str] = []
    if name_col:
        order_bits.append(f"{v_alias}.{name_col}")
    period = _pick_col(view_cols, ("period_label", "payroll_year"))
    if period:
        order_bits.append(f"{v_alias}.{period} DESC NULLS LAST")
    order_sql = f"ORDER BY {', '.join(order_bits)}" if order_bits else ""
    where_name = f"{v_alias}.{name_col} IS NOT NULL" if name_col else "1=1"
    select_sql = ",\n".join(select_parts)
    _ = question
    return f"""SELECT
{select_sql}
{from_clause}
WHERE {where_name}
{order_sql}
LIMIT {max_rows};"""


def _build_from_mart_and_payroll_group(
    grounding: SchemaGrounding,
    emp_short: str,
    *,
    max_rows: int,
) -> Optional[str]:
    have = _grounded_shorts(grounding)
    if "dim_payroll_group" not in have:
        return None
    emp_cols = _cols_for_short(grounding, emp_short)
    pg_cols = _cols_for_short(grounding, "dim_payroll_group")
    emp_schema = _schema_for_short(grounding, emp_short)
    pg_schema = _schema_for_short(grounding, "dim_payroll_group")
    m_alias = "m"
    pg_alias = "pg"

    select_parts: list[str] = []
    name_col = _pick_col(
        emp_cols,
        ("emp_fullname", "full_name", "employee_name", "emp_name"),
    )
    if name_col:
        select_parts.append(f"    {m_alias}.{name_col} AS employee_name")
    id_col = _pick_col(emp_cols, ("emp_no", "employee_no", "employee_id"))
    if id_col:
        select_parts.append(f"    {m_alias}.{id_col} AS employee_id")
    branch_col = _pick_col(emp_cols, ("location_name", "branch_name", "branch"))
    if branch_col:
        select_parts.append(f"    {m_alias}.{branch_col} AS branch")
    sal_col = _pick_col(emp_cols, ("basic_salary",))
    if sal_col:
        select_parts.append(f"    {m_alias}.{sal_col} AS basic_salary")

    join_on = _join_payroll_group_on(m_alias, emp_cols, pg_alias, pg_cols)
    if not join_on:
        return None
    _append_payroll_group_select(select_parts, pg_alias, pg_cols)

    if len(select_parts) < 4:
        return None

    is_current = _pick_col(emp_cols, ("is_current",))
    is_current_filter = (
        f"\n  AND {m_alias}.{is_current} IS TRUE" if is_current else ""
    )

    order_sql = f"ORDER BY {m_alias}.{name_col}" if name_col else ""
    where_name = f"{m_alias}.{name_col} IS NOT NULL" if name_col else "1=1"
    select_sql = ",\n".join(select_parts)
    return f"""SELECT
{select_sql}
FROM {emp_schema}.{emp_short} {m_alias}
LEFT JOIN {pg_schema}.dim_payroll_group {pg_alias}
    ON {join_on}
WHERE {where_name}{is_current_filter}
{order_sql}
LIMIT {max_rows};"""


def build_payroll_sql_from_grounding(
    question: str,
    grounding: SchemaGrounding,
    *,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    """Build payroll summary SQL using only allowlisted tables and columns."""
    if not grounding.columns_by_table:
        return None

    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    view_short = _pick_payroll_view(grounding)
    if view_short:
        built = _build_from_vw_payroll_summary(
            question, grounding, view_short, max_rows=limit
        )
        if built:
            return built

    emp_short = _pick_employee_table(grounding)
    if emp_short:
        built = _build_from_mart_and_payroll_group(grounding, emp_short, max_rows=limit)
        if built:
            return built

    have = _grounded_shorts(grounding)
    if emp_short and have & set(_PAYROLL_FACT_PRIORITY):
        for fact_short in _PAYROLL_FACT_PRIORITY:
            if fact_short not in have:
                continue
            return _build_emp_fact_payroll_sql(
                grounding, emp_short, fact_short, max_rows=limit
            )
    return None


def _build_emp_fact_payroll_sql(
    grounding: SchemaGrounding,
    emp_short: str,
    fact_short: str,
    *,
    max_rows: int,
) -> Optional[str]:
    emp_cols = _cols_for_short(grounding, emp_short)
    fact_cols = _cols_for_short(grounding, fact_short)
    emp_schema = _schema_for_short(grounding, emp_short)
    fact_schema = _schema_for_short(grounding, fact_short)
    e_alias = "e"
    p_alias = "p"
    join_on = _join_employee_to_fact(e_alias, emp_cols, p_alias, fact_cols)
    if not join_on:
        return None

    select_parts: list[str] = []
    name_col = _pick_col(
        emp_cols,
        ("emp_fullname", "full_name", "employee_name", "emp_name"),
    )
    if name_col:
        select_parts.append(f"    {e_alias}.{name_col} AS employee_name")
    id_col = _pick_col(emp_cols, ("emp_no", "employee_no", "employee_id"))
    if id_col:
        select_parts.append(f"    {e_alias}.{id_col} AS employee_id")
    branch_col = _pick_col(emp_cols, ("location_name", "branch_name", "branch"))
    if branch_col:
        select_parts.append(f"    {e_alias}.{branch_col} AS branch")
    sal_emp = _pick_col(emp_cols, ("basic_salary",))
    sal_fact = _pick_col(fact_cols, ("basic_salary", "gross_salary"))
    if sal_fact:
        select_parts.append(f"    {p_alias}.{sal_fact} AS basic_salary")
    elif sal_emp:
        select_parts.append(f"    {e_alias}.{sal_emp} AS basic_salary")

    from_clause = (
        f"FROM {emp_schema}.{emp_short} {e_alias}\n"
        f"INNER JOIN {fact_schema}.{fact_short} {p_alias}\n"
        f"    ON {join_on}"
    )
    have = _grounded_shorts(grounding)
    if "dim_payroll_group" in have:
        pg_cols = _cols_for_short(grounding, "dim_payroll_group")
        pg_schema = _schema_for_short(grounding, "dim_payroll_group")
        pg_alias = "pg"
        pg_join = _join_payroll_group_on(e_alias, emp_cols, pg_alias, pg_cols)
        if pg_join:
            from_clause += (
                f"\nLEFT JOIN {pg_schema}.dim_payroll_group {pg_alias}\n"
                f"    ON {pg_join}"
            )
            _append_payroll_group_select(select_parts, pg_alias, pg_cols)

    if len(select_parts) < 3:
        return None

    order_bits: list[str] = []
    period = _pick_col(fact_cols, ("period_label", "payroll_year"))
    if period:
        order_bits.append(f"{p_alias}.{period} DESC NULLS LAST")
    if name_col:
        order_bits.append(f"{e_alias}.{name_col}")
    order_sql = f"ORDER BY {', '.join(order_bits)}" if order_bits else ""
    where_name = f"{e_alias}.{name_col} IS NOT NULL" if name_col else "1=1"
    select_sql = ",\n".join(select_parts)
    return f"""SELECT
{select_sql}
{from_clause}
WHERE {where_name}
{order_sql}
LIMIT {max_rows};"""


def try_build_payroll_detail_report_sql(
    question: str,
    *,
    grounded_short_names: Optional[list[str]] = None,
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[str]:
    _ = grounded_short_names
    if not looks_like_payroll_detail_report(question):
        return None
    if grounding and grounding.columns_by_table:
        built = build_payroll_sql_from_grounding(question, grounding)
        if built:
            return built
    return None
