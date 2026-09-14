"""
Tier C step 1: produce a structured query plan (no SQL) before SQL generation.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from .. import config as dm_config
from ..llm.llm_client import LlmRole, call_llm
from ..schema_broker import SchemaGrounding
from .artifacts import QueryPlan

logger = logging.getLogger("ai_services.datamart.query_plan")

_PLAN_SYSTEM = """You are an analytics SQL planner for PostgreSQL HR data marts.
Output ONLY a single JSON object (no markdown fences) with this shape:
{
  "tables": ["short_table_names from the allowlist only"],
  "joins": ["schema.table.col = schema.table.col"],
  "filters": ["human-readable filter descriptions"],
  "select_columns": ["output column labels the user asked for"],
  "aggregations": null,
  "order_limit": "ORDER BY ... LIMIT n"
}
Rules:
- Use ONLY tables from the grounded allowlist.
- Do NOT write SQL — planning only.
- If the question is unclear, set filters to ["NEEDS_CLARIFICATION: <what to ask>"].
"""

_PLAN_USER_TEMPLATE = """Question:
{question}

Grounded tables (use only these):
{tables}

Domain: {domain}
"""


def _extract_json_object(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def parse_query_plan(llm_output: str, *, allowed_tables: list[str]) -> Optional[QueryPlan]:
    data = _extract_json_object(llm_output)
    if not data:
        return None
    allowed_lower = {t.lower() for t in allowed_tables}

    def _str_list(key: str) -> list[str]:
        raw = data.get(key) or []
        if not isinstance(raw, list):
            return []
        return [str(x).strip() for x in raw if str(x).strip()]

    tables = _str_list("tables")
    tables = [t for t in tables if t.lower() in allowed_lower] or list(allowed_tables[:6])

    plan = QueryPlan(
        tables=tables,
        joins=_str_list("joins"),
        filters=_str_list("filters"),
        select_columns=_str_list("select_columns"),
        aggregations=data.get("aggregations")
        if isinstance(data.get("aggregations"), dict)
        else None,
        order_limit=str(data.get("order_limit") or "").strip(),
        raw_json=json.dumps(data, ensure_ascii=False)[:4000],
    )
    return plan


def clarification_from_plan(plan: Optional[QueryPlan]) -> Optional[str]:
    """Extract user-facing clarification text when the plan cannot proceed."""
    if not plan:
        return None
    for filt in plan.filters:
        text = str(filt).strip()
        if text.upper().startswith("NEEDS_CLARIFICATION:"):
            return text.split(":", 1)[1].strip()
    return None


def build_query_plan(
    question: str,
    *,
    grounding: SchemaGrounding,
    domain: str | None = None,
) -> Optional[QueryPlan]:
    """Call LLM once for a JSON plan; return None on failure (Tier C falls back to direct SQL)."""
    if not dm_config.DATAMART_TIER_C_QUERY_PLAN:
        return None
    tables = grounding.table_short_names
    if not tables:
        return None
    user = _PLAN_USER_TEMPLATE.format(
        question=question.strip(),
        tables=", ".join(tables),
        domain=domain or "unknown",
    )
    try:
        raw = call_llm(_PLAN_SYSTEM, user, role=LlmRole.CHAT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Query plan LLM failed: %s", exc)
        return None
    plan = parse_query_plan(raw, allowed_tables=tables)
    if plan and any(f.startswith("NEEDS_CLARIFICATION:") for f in plan.filters):
        logger.info("Query plan requested clarification: %s", plan.filters)
    return plan
