"""
Deterministic recruitment pipeline list SQL (candidates + pipeline fact).

Used when the LLM returns SQL:NONE for hiring / candidate list questions.
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import MAX_RESULT_ROWS
from .metric_templates import question_wants_row_detail
from .recruitment_hire_proxy_sql import try_build_recruitment_hire_proxy_sql
from ..workspace.runtime_context import mart_schema_for_hints
from ..schema_broker import SchemaGrounding

_RECRUITMENT_RE = re.compile(
    r"\b(?:recruitment|recruit|hiring|candidate|candidates|applicant|"
    r"pipeline|requisition|job\s+offer|linkedin|referral)\b",
    re.IGNORECASE,
)

_FACT = "fact_recruitment_pipeline"
_DIM_CAND = "dim_candidate"
_DIM_BRANCH = "dim_org_unit"


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


def looks_like_recruitment_pipeline_report(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
) -> bool:
    q = (question or "").strip()
    if not q or not _RECRUITMENT_RE.search(q):
        return False
    if not question_wants_row_detail(q) and not re.search(
        r"\b(?:report|list|show|prepare|including)\b", q, re.I
    ):
        return False
    if grounding is None:
        return True
    has_fact = _qualified_for_short(grounding, _FACT) is not None
    has_cand = _qualified_for_short(grounding, _DIM_CAND) is not None
    has_hire_proxy = _qualified_for_short(grounding, "fct_lifecycle_event") is not None
    return has_fact or has_cand or has_hire_proxy


def _source_filter_sql(question: str, source_col: str, alias: str) -> str:
    q = question.lower()
    parts: list[str] = []
    if "linkedin" in q:
        parts.append(f"{alias}.{source_col} ILIKE '%linkedin%'")
    if "referral" in q:
        parts.append(
            f"({alias}.{source_col} ILIKE '%referral%' "
            f"OR {alias}.{source_col} ILIKE '%employee referral%')"
        )
    if not parts:
        return ""
    return " AND (" + " OR ".join(parts) + ")"


def _joining_window_filter(join_col: str, alias: str, days: int = 60) -> str:
    return (
        f" AND {alias}.{join_col} >= CURRENT_DATE "
        f"AND {alias}.{join_col} < CURRENT_DATE + INTERVAL '{days} days'"
    )


def try_build_recruitment_pipeline_sql(
    question: str,
    *,
    grounding: SchemaGrounding,
    max_rows: Optional[int] = None,
) -> Optional[str]:
    if not looks_like_recruitment_pipeline_report(question, grounding=grounding):
        return None

    fact_q = _qualified_for_short(grounding, _FACT)
    cand_q = _qualified_for_short(grounding, _DIM_CAND)
    if not fact_q and not cand_q:
        return try_build_recruitment_hire_proxy_sql(question, grounding=grounding)

    if not fact_q:
        proxy = try_build_recruitment_hire_proxy_sql(question, grounding=grounding)
        if proxy:
            return proxy

    # Prefer fact + dim_candidate join; single-table fallback on whichever exists.
    if fact_q:
        fact_schema = _schema_for_short(grounding, _FACT)
        fact_cols = _cols_for_short(grounding, _FACT)
        fact_alias = "rp"
        cand_alias = "c"
        cand_cols = _cols_for_short(grounding, _DIM_CAND) if cand_q else []

        name_col = _pick_col(
            cand_cols or fact_cols,
            ("candidate_name", "full_name", "applicant_name"),
        )
        email_col = _pick_col(
            cand_cols or fact_cols,
            ("email", "contact_email", "candidate_email"),
        )
        source_col = _pick_col(
            fact_cols,
            (
                "recruitment_source",
                "source",
                "source_name",
                "hiring_source",
            ),
        ) or _pick_col(cand_cols, ("recruitment_source", "source"))
        appt_col = _pick_col(
            fact_cols,
            ("appointment_date", "interview_date", "offer_date"),
        )
        join_col = _pick_col(
            fact_cols,
            (
                "expected_joining_date",
                "joining_date",
                "expected_join_date",
                "start_date",
            ),
        )
        branch_col_fact = _pick_col(
            fact_cols, ("branch_name", "assigned_branch", "location_name")
        )

        select_parts: list[str] = []
        name_from = cand_alias if cand_q and name_col in cand_cols else fact_alias
        if name_col:
            select_parts.append(f"{name_from}.{name_col} AS candidate_name")
        if email_col:
            email_from = cand_alias if cand_q and email_col in cand_cols else fact_alias
            select_parts.append(f"{email_from}.{email_col} AS contact_email")
        if source_col:
            select_parts.append(f"{fact_alias}.{source_col} AS recruitment_source")
        if appt_col:
            select_parts.append(f"{fact_alias}.{appt_col} AS appointment_date")
        if join_col:
            select_parts.append(f"{fact_alias}.{join_col} AS expected_joining_date")

        join_sql = ""
        if cand_q:
            cand_schema = _schema_for_short(grounding, _DIM_CAND)
            cand_key = _pick_col(cand_cols, ("candidate_id",))
            fact_key = _pick_col(fact_cols, ("candidate_id",))
            if cand_key and fact_key:
                join_sql = (
                    f"\nJOIN {cand_schema}.{_DIM_CAND} {cand_alias}\n"
                    f"  ON {cand_alias}.{cand_key} = {fact_alias}.{fact_key}"
                )
            else:
                join_sql = f"\nLEFT JOIN {cand_schema}.{_DIM_CAND} {cand_alias} ON TRUE"

        branch_join = ""
        if branch_col_fact:
            select_parts.append(f"{fact_alias}.{branch_col_fact} AS assigned_branch")
        elif _DIM_BRANCH in {s.lower() for s in grounding.table_short_names}:
            org_cols = _cols_for_short(grounding, _DIM_BRANCH)
            branch_name = _pick_col(org_cols, ("org_unit_name", "branch_name", "name"))
            branch_key_fact = _pick_col(
                fact_cols, ("branch_id", "org_unit_id", "assigned_branch_id")
            )
            org_key = _pick_col(org_cols, ("org_unit_id", "branch_id", "source_org_id"))
            if branch_name and branch_key_fact and org_key:
                org_schema = _schema_for_short(grounding, _DIM_BRANCH)
                select_parts.append(f"ou.{branch_name} AS assigned_branch")
                branch_join = (
                    f"\nLEFT JOIN {org_schema}.{_DIM_BRANCH} ou\n"
                    f"  ON ou.{org_key}::text = {fact_alias}.{branch_key_fact}::text"
                )

        if not select_parts:
            return None

        where_parts = ["1=1"]
        if source_col:
            src_filter = _source_filter_sql(question, source_col, fact_alias)
            if src_filter:
                where_parts.append(src_filter.strip().lstrip("AND").strip())
        if join_col and re.search(r"\b(?:next|within)\s+(\d+)\s+days?\b", question, re.I):
            m = re.search(r"\b(?:next|within)\s+(\d+)\s+days?\b", question, re.I)
            days = int(m.group(1)) if m else 60
            where_parts.append(
                _joining_window_filter(join_col, fact_alias, days).strip().lstrip("AND")
            )
        elif join_col and re.search(r"\bnext\s+60\s+days\b", question, re.I):
            where_parts.append(
                _joining_window_filter(join_col, fact_alias, 60).strip().lstrip("AND")
            )

        limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
        select_sql = ",\n    ".join(select_parts)
        where_sql = "\n  AND ".join(where_parts)
        return f"""SELECT
    {select_sql}
FROM {fact_schema}.{_FACT} {fact_alias}{join_sql}{branch_join}
WHERE {where_sql}
ORDER BY {fact_alias}.{join_col or appt_col or name_col or '1'}
LIMIT {limit};"""

    # dim_candidate only
    cand_schema = _schema_for_short(grounding, _DIM_CAND)
    cand_cols = _cols_for_short(grounding, _DIM_CAND)
    name_col = _pick_col(cand_cols, ("candidate_name", "full_name"))
    if not name_col:
        return None
    limit = max_rows if max_rows is not None else MAX_RESULT_ROWS
    return f"""SELECT
    c.{name_col} AS candidate_name
FROM {cand_schema}.{_DIM_CAND} c
LIMIT {limit};"""
