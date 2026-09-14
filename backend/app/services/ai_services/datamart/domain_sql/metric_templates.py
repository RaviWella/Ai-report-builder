"""Verified SQL templates from semantic catalog metrics (deterministic Tier-A answers)."""
from __future__ import annotations

import re
from typing import Optional

from ..workspace.runtime_context import mart_schema_for_hints
from ..semantic.semantic_layer import SemanticResolution, _load_catalog, _match_metrics, _question_tokens
from ..validation.validation_models import RetrievalValidation, ValidationStatus

_TOP_N_RE = re.compile(
    r"\b(?:top|first|highest|lowest|bottom)\s+(\d+)\b",
    re.IGNORECASE,
)

# Questions that need multi-column rows / joins — never use a single-metric COUNT template.
_DETAIL_REPORT_RE = re.compile(
    r"\b("
    r"generate|report|listing|list\b|combine|combining|breakdown|detail|detailed|"
    r"include|including|show\s+me|give\s+me|export|spreadsheet|table\s+of|"
    r"by\s+department|by\s+branch|org\s+chart|workforce\s+report|workforce\s+data"
    r")\b",
    re.IGNORECASE,
)

_SCALAR_COUNT_RE = re.compile(
    r"\b(?:how\s+many|count|number\s+of|total\s+number|headcount|head\s+count|"
    r"employee\s+count|workforce\s+size)\b",
    re.IGNORECASE,
)

_AGGREGATE_ONLY_SQL_RE = re.compile(
    r"^\s*select\s+count\s*\(",
    re.IGNORECASE | re.DOTALL,
)


def question_wants_row_detail(question: str) -> bool:
    """True when the user expects multiple attributes or rows, not a single KPI."""
    q = question.strip()
    if not q:
        return False
    if _DETAIL_REPORT_RE.search(q):
        return True
    # "employee name, company, branch" style lists
    if q.count(",") >= 2:
        return True
    if len(re.findall(r"\band\b", q, re.IGNORECASE)) >= 2:
        return True
    # Several explicit field phrases
    field_hints = re.findall(
        r"\b(?:name|id|company|branch|department|designation|manager|title|email)\b",
        q,
        re.IGNORECASE,
    )
    if len(set(h.lower() for h in field_hints)) >= 3:
        return True
    if re.search(r"\b(?:show|list|display|get)\b", q, re.IGNORECASE) and re.search(
        r"\bemployees?\b", q, re.IGNORECASE
    ):
        return True
    return False


def question_is_scalar_metric_intent(question: str, metric_name: str) -> bool:
    """Only use verified SQL when the question clearly asks for that one metric."""
    if question_wants_row_detail(question):
        return False
    q = question.lower()
    mn = metric_name.lower()
    if mn in ("employee_count", "headcount"):
        if _SCALAR_COUNT_RE.search(question):
            return True
        # Explicit metric name only (not generic "employees" in a report)
        if mn.replace("_", " ") in q or mn in q:
            return True
        return False
    if mn == "top_paid":
        return bool(_TOP_N_RE.search(question) or ("top" in q and "salary" in q))
    if mn == "average_salary":
        return bool(
            re.search(r"\b(?:average|avg|mean)\b", q, re.IGNORECASE)
            and "salary" in q
        )
    return False


def is_scalar_aggregate_sql(sql: Optional[str]) -> bool:
    if not sql or not sql.strip():
        return False
    return bool(_AGGREGATE_ONLY_SQL_RE.match(sql.strip()))


def sql_mismatches_detail_question(question: str, sql: Optional[str]) -> bool:
    """COUNT-only SQL cannot answer a multi-column workforce report."""
    return question_wants_row_detail(question) and is_scalar_aggregate_sql(sql)


def can_use_verified_metric_sql(
    question: str,
    retrieval: Optional[RetrievalValidation],
) -> bool:
    if retrieval is None:
        return True
    if retrieval.status == ValidationStatus.INSUFFICIENT:
        return False
    if retrieval.status == ValidationStatus.AMBIGUOUS and retrieval.missing_tables:
        return False
    if question_wants_row_detail(question):
        return False
    return True


def try_resolve_verified_metric_sql(
    question: str,
    semantics: Optional[SemanticResolution] = None,
    retrieval: Optional[RetrievalValidation] = None,
) -> Optional[tuple[str, str, str]]:
    """
    If question matches a catalog metric with ``verified_sql``, return (sql, metric_id, narrative).

    Only for simple scalar questions with sufficient retrieval context.
    """
    if not can_use_verified_metric_sql(question, retrieval):
        return None

    tokens = _question_tokens(question)
    matched = _match_metrics(question, tokens)
    with_template = [
        (n, s)
        for n, s in matched
        if isinstance(s.get("verified_sql"), str) and s["verified_sql"].strip()
    ]
    if with_template:
        matched = with_template + [(n, s) for n, s in matched if (n, s) not in with_template]
    if not matched and semantics:
        for name in semantics.metrics_matched:
            spec = (_load_catalog().get("metrics") or {}).get(name) or {}
            if isinstance(spec, dict):
                matched.append((name, spec))
    if not matched:
        return None

    schema = mart_schema_for_hints()
    limit_m = _TOP_N_RE.search(question)
    limit_n = int(limit_m.group(1)) if limit_m else 10
    q_lower = question.lower()

    if limit_m:
        matched.sort(key=lambda item: 0 if item[0] == "top_paid" else 1)
    if "headcount" in q_lower:
        matched.sort(key=lambda item: 0 if item[0] == "headcount" else 1)

    for metric_name, spec in matched:
        if not question_is_scalar_metric_intent(question, metric_name):
            continue
        template = spec.get("verified_sql")
        if not isinstance(template, str) or not template.strip():
            continue
        sql = template.format(limit=limit_n, schema=schema).strip()
        if not sql.upper().startswith("SELECT"):
            continue
        narrative = (
            f"Using verified catalog metric '{metric_name.replace('_', ' ')}' "
            f"(deterministic SQL template)."
        )
        return sql, metric_name, narrative
    return None
