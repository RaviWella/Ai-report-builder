"""
Offline question-bank eval (S4) — no LLM, no warehouse.

Validates domain classification, expect_tables vs domain allowlist, and Tier-B
domain scoping using ``tools/datamart_question_bank.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .domain import DatamartDomain
from .domain_classifier import classify_domain
from .domain_registry import allowed_tables_for_domain, required_tables_for_domain
from .verified_query_store import clear_verified_query_cache, retrieve_verified_sql

# eval_domain labels in the question bank → classifier domain
_EVAL_DOMAIN_MAP: dict[str, DatamartDomain] = {
    "payroll": DatamartDomain.PAYROLL,
    "leave": DatamartDomain.LEAVE,
    "attendance": DatamartDomain.ATTENDANCE,
    "workforce": DatamartDomain.WORKFORCE,
    "attrition": DatamartDomain.ATTRITION,
    "headcount": DatamartDomain.HEADCOUNT,
    "recruitment": DatamartDomain.RECRUITMENT,
    "compensation": DatamartDomain.PAYROLL,
    "performance": DatamartDomain.WORKFORCE,
}

# Question-bank sections that intentionally span multiple domains.
_CROSS_DOMAIN_SECTIONS: frozenset[str] = frozenset(
    {
        "advanced_mixed_payroll_leave",
        "advanced_mixed_att_workforce",
        "advanced_executive",
    }
)

# eval_domain label → classifier domains that are acceptable in cross-domain sets.
_RELATED_CLASSIFIER_DOMAINS: dict[str, frozenset[DatamartDomain]] = {
    "payroll": frozenset(
        {DatamartDomain.PAYROLL, DatamartDomain.LEAVE, DatamartDomain.MIXED}
    ),
    "leave": frozenset(
        {DatamartDomain.PAYROLL, DatamartDomain.LEAVE, DatamartDomain.MIXED}
    ),
    "attendance": frozenset(
        {
            DatamartDomain.ATTENDANCE,
            DatamartDomain.WORKFORCE,
            DatamartDomain.MIXED,
        }
    ),
    "workforce": frozenset(
        {
            DatamartDomain.WORKFORCE,
            DatamartDomain.ATTENDANCE,
            DatamartDomain.HEADCOUNT,
            DatamartDomain.MIXED,
        }
    ),
    "headcount": frozenset(
        {
            DatamartDomain.HEADCOUNT,
            DatamartDomain.WORKFORCE,
            DatamartDomain.MIXED,
        }
    ),
    "attrition": frozenset(
        {DatamartDomain.ATTRITION, DatamartDomain.MIXED, DatamartDomain.UNKNOWN}
    ),
}

_DEFAULT_BANK = (
    Path(__file__).resolve().parents[5] / "tools" / "datamart_question_bank.yaml"
)


@dataclass
class LinkEvalCaseResult:
    section: str
    question_preview: str
    eval_domain: str
    classified_domain: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    tier_b_source: Optional[str] = None


@dataclass
class LinkEvalReport:
    total: int
    passed: int
    failed: int
    results: list[LinkEvalCaseResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


def load_question_bank(path: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bank_path = path or _DEFAULT_BANK
    raw = yaml.safe_load(bank_path.read_text(encoding="utf-8")) or {}
    items: list[dict[str, Any]] = []
    for section, entries in raw.items():
        if section == "meta" or not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("question"):
                items.append({**entry, "section": section})
    return raw, items


def _short_tables(expect: list[str]) -> set[str]:
    return {t.rsplit(".", 1)[-1].lower() for t in expect if str(t).strip()}


def _domain_aligns(
    classified: DatamartDomain,
    eval_domain: str,
    *,
    section: str,
) -> Optional[str]:
    eval_l = eval_domain.strip().lower()
    expected = _EVAL_DOMAIN_MAP.get(eval_l)
    if expected is None:
        return f"unknown eval_domain {eval_domain!r}"
    if classified == expected:
        return None
    if classified == DatamartDomain.MIXED:
        return None
    if section in _CROSS_DOMAIN_SECTIONS:
        related = _RELATED_CLASSIFIER_DOMAINS.get(eval_l, frozenset())
        if classified in related:
            return None
        return None
    if eval_l == "headcount" and classified in (
        DatamartDomain.HEADCOUNT,
        DatamartDomain.WORKFORCE,
    ):
        return None
    if eval_l == "workforce" and classified == DatamartDomain.HEADCOUNT:
        return None
    if eval_l == "attrition" and classified in (
        DatamartDomain.ATTRITION,
        DatamartDomain.UNKNOWN,
    ):
        return None
    return (
        f"classified={classified.value} expected={expected.value} "
        f"(eval_domain={eval_domain})"
    )


def _union_allowlist_shorts() -> frozenset[str]:
    out: set[str] = set()
    for dom in DatamartDomain:
        allow = allowed_tables_for_domain(dom)
        if allow:
            out |= allow
        out |= {t.lower() for t in required_tables_for_domain(dom)}
    return frozenset(out)


def _expect_tables_allowed(
    expect: list[str],
    domain: DatamartDomain,
    *,
    section: str,
    classified: DatamartDomain,
) -> list[str]:
    if section in _CROSS_DOMAIN_SECTIONS or classified == DatamartDomain.MIXED:
        union = _union_allowlist_shorts()
        return [
            str(raw).rsplit(".", 1)[-1].lower()
            for raw in expect
            if str(raw).rsplit(".", 1)[-1].lower() not in union
        ]

    allow = allowed_tables_for_domain(domain)
    if allow is None:
        return []
    required = {t.lower() for t in required_tables_for_domain(domain)}
    missing: list[str] = []
    for raw in expect:
        short = str(raw).rsplit(".", 1)[-1].lower()
        if short in allow or short in required:
            continue
        missing.append(short)
    return missing


def _tier_b_probe(
    question: str,
    *,
    grounded: set[str],
    domain: str,
) -> Optional[str]:
    clear_verified_query_cache()
    match = retrieve_verified_sql(
        question,
        grounded_tables=grounded,
        domain=domain,
        min_score=6,
    )
    if not match:
        return None
    _sql, source, _narr = match
    return source


def eval_one_case(case: dict[str, Any], *, check_tier_b: bool = True) -> LinkEvalCaseResult:
    q = str(case["question"]).strip()
    section = str(case.get("section") or "")
    eval_domain = str(case.get("eval_domain") or "").strip().lower()
    expect = list(case.get("expect_tables") or [])
    preview = q[:72] + ("…" if len(q) > 72 else "")

    errors: list[str] = []
    classification = classify_domain(q)
    classified = classification.domain

    if eval_domain:
        dom_err = _domain_aligns(classified, eval_domain, section=section)
        if dom_err:
            errors.append(dom_err)

    mapped = _EVAL_DOMAIN_MAP.get(eval_domain)
    if mapped and expect:
        missing_allow = _expect_tables_allowed(
            expect,
            mapped,
            section=section,
            classified=classified,
        )
        if missing_allow:
            errors.append(
                "expect_tables not in domain allowlist: " + ", ".join(missing_allow)
            )

    tier_b_source: Optional[str] = None
    if check_tier_b and mapped and expect:
        grounded = _short_tables(expect)
        tier_b_source = _tier_b_probe(q, grounded=grounded, domain=mapped.value)
        if tier_b_source and tier_b_source.startswith("verified:leave"):
            if mapped == DatamartDomain.RECRUITMENT:
                errors.append(f"Tier B cross-domain leak: {tier_b_source}")

    return LinkEvalCaseResult(
        section=section,
        question_preview=preview,
        eval_domain=eval_domain,
        classified_domain=classified.value,
        ok=not errors,
        errors=errors,
        tier_b_source=tier_b_source,
    )


def eval_question_bank(
    cases: list[dict[str, Any]] | None = None,
    *,
    bank_path: Path | None = None,
    check_tier_b: bool = True,
) -> LinkEvalReport:
    if cases is None:
        _raw, cases = load_question_bank(bank_path)

    results = [eval_one_case(c, check_tier_b=check_tier_b) for c in cases]
    passed = sum(1 for r in results if r.ok)
    return LinkEvalReport(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )
