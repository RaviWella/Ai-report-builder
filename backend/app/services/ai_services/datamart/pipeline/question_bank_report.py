"""S6: enrich live question-bank eval rows with pipeline domain + SQL tier."""
from __future__ import annotations

from typing import Any, Optional

from .domain_classifier import classify_domain
from .link_eval import _domain_aligns
from .sql_resolver import _tier_label


def pipeline_fields_for_question(
    case: dict[str, Any],
    *,
    sql_source: Optional[str],
    report_spec_domain: str,
) -> dict[str, Any]:
    """Offline classifier + tier label for eval reporting (no extra LLM)."""
    q = str(case.get("question") or "").strip()
    classification = classify_domain(q)
    eval_domain = str(case.get("eval_domain") or "").strip().lower()
    section = str(case.get("section") or "")
    domain_err = (
        _domain_aligns(
            classification.domain,
            eval_domain,
            section=section,
        )
        if eval_domain
        else None
    )
    tier = _tier_label(sql_source) if sql_source else None
    return {
        "classified_domain": classification.domain.value,
        "eval_domain": eval_domain or report_spec_domain,
        "domain_match": domain_err is None,
        "domain_note": domain_err,
        "sql_tier": tier,
        "sql_source": sql_source,
    }
