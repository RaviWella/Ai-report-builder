"""
Classify the business domain of a natural-language question.

Priority rules prevent payroll/headcount topics from winning when the user asks
about recruitment (e.g. LinkedIn, referrals, candidates).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import DatamartDomain

# (domain, weight, pattern)
_DOMAIN_PATTERNS: list[tuple[DatamartDomain, int, re.Pattern[str]]] = [
    (
        DatamartDomain.RECRUITMENT,
        12,
        re.compile(
            r"\b(?:recruitment|recruit|hiring|candidate|candidates|applicant|"
            r"pipeline|requisition|linkedin|referral|referrals|appointment\s+date|"
            r"joining\s+date|expected\s+joining|time\s+to\s+hire|job\s+offer)\b",
            re.I,
        ),
    ),
    (
        DatamartDomain.LEAVE,
        10,
        re.compile(
            r"\b(?:leave|absence|vacation|pto|sick\s+leave|annual\s+leave)\b",
            re.I,
        ),
    ),
    (
        DatamartDomain.ATTENDANCE,
        10,
        re.compile(
            r"\b(?:attendance|present\s+days|absent\s+days|late\s+events?|overtime)\b",
            re.I,
        ),
    ),
    (
        DatamartDomain.PAYROLL,
        9,
        re.compile(
            r"\b(?:payroll|payslip|pay\s+slip|gross\s+pay|net\s+pay|basic\s+salary|"
            r"deduction|epf|etf)\b",
            re.I,
        ),
    ),
    (
        DatamartDomain.ATTRITION,
        9,
        re.compile(
            r"\b(?:attrition|turnover|separation|resignation|exit|"
            r"lifecycle|tenure|employment\s+monthly)\b",
            re.I,
        ),
    ),
    (
        DatamartDomain.HEADCOUNT,
        8,
        re.compile(
            r"\b(?:headcount|head\s+count|new\s+hires?|hiring\s+trend)\b",
            re.I,
        ),
    ),
    (
        DatamartDomain.WORKFORCE,
        7,
        re.compile(
            r"\b(?:workforce|employee\s+roster|org\s+chart|reporting\s+manager|"
            r"designation|department)\b",
            re.I,
        ),
    ),
]

# Recruitment-specific boosts (user screenshot case).
_RECRUITMENT_STRONG = re.compile(
    r"\b(?:linkedin|referral|referrals|candidate|candidates|recruitment\s+pipeline|"
    r"expected\s+to\s+join)\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class DomainClassification:
    domain: DatamartDomain
    confidence: float
    scores: dict[str, int]


def classify_domain(question: str, *, topics_matched: list[str] | None = None) -> DomainClassification:
    q = (question or "").strip()
    if not q:
        return DomainClassification(
            domain=DatamartDomain.UNKNOWN,
            confidence=0.0,
            scores={},
        )

    scores: dict[DatamartDomain, int] = {d: 0 for d in DatamartDomain}
    for domain, weight, pattern in _DOMAIN_PATTERNS:
        if pattern.search(q):
            scores[domain] += weight

    if _RECRUITMENT_STRONG.search(q):
        scores[DatamartDomain.RECRUITMENT] += 15

    if topics_matched:
        topic_map = {
            "recruitment": DatamartDomain.RECRUITMENT,
            "leave": DatamartDomain.LEAVE,
            "attendance": DatamartDomain.ATTENDANCE,
            "payroll": DatamartDomain.PAYROLL,
            "employee_information": DatamartDomain.WORKFORCE,
            "employee_lifecycle": DatamartDomain.ATTRITION,
        }
        for topic in topics_matched:
            dom = topic_map.get(topic)
            if dom:
                scores[dom] += 6

    ranked = sorted(
        ((d, s) for d, s in scores.items() if s > 0 and d != DatamartDomain.UNKNOWN),
        key=lambda x: -x[1],
    )
    if not ranked:
        return DomainClassification(
            domain=DatamartDomain.UNKNOWN,
            confidence=0.0,
            scores={d.value: s for d, s in scores.items()},
        )

    top_domain, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if len(ranked) >= 2 and second_score >= top_score * 0.85:
        return DomainClassification(
            domain=DatamartDomain.MIXED,
            confidence=min(0.9, top_score / max(top_score + second_score, 1)),
            scores={d.value: s for d, s in scores.items()},
        )

    confidence = min(1.0, top_score / 20.0)
    return DomainClassification(
        domain=top_domain,
        confidence=confidence,
        scores={d.value: s for d, s in scores.items()},
    )
