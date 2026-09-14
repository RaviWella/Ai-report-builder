"""
S4 CI: question bank domain alignment + allowlist + Tier-B cross-domain guard (no warehouse).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_services.datamart.pipeline.domain import DatamartDomain
from app.services.ai_services.datamart.pipeline.domain_classifier import classify_domain
from app.services.ai_services.datamart.pipeline.link_eval import (
    eval_question_bank,
    load_question_bank,
)
from app.services.ai_services.datamart.pipeline.verified_query_store import (
    clear_verified_query_cache,
    retrieve_verified_sql,
)

BANK_PATH = Path(__file__).resolve().parents[2] / "tools" / "datamart_question_bank.yaml"

RECRUITMENT_QUESTION = (
    "Prepare a recruitment pipeline report showing candidates sourced through LinkedIn "
    "and employee referrals, including candidate name, contact email, recruitment source, "
    "appointment date, expected joining date, and assigned branch. Include only candidates "
    "who are expected to join within the next 60 days."
)


@pytest.fixture(scope="module")
def bank_cases():
    _raw, items = load_question_bank(BANK_PATH)
    return items


def test_question_bank_link_eval_passes_offline(bank_cases):
    report = eval_question_bank(bank_cases, bank_path=BANK_PATH)
    failures = [
        f"{r.section}: {r.errors} — {r.question_preview[:50]}"
        for r in report.results
        if not r.ok
    ]
    assert report.success, failures


def test_recruitment_bank_rows_classify_recruitment(bank_cases):
    recruitment = [c for c in bank_cases if c.get("eval_domain") == "recruitment"]
    assert len(recruitment) >= 3
    for case in recruitment:
        dom = classify_domain(case["question"].strip()).domain
        assert dom in (DatamartDomain.RECRUITMENT, DatamartDomain.MIXED), case["section"]


def test_tier_b_no_leave_match_for_recruitment_question():
    clear_verified_query_cache()
    grounded = {
        "fact_recruitment_pipeline",
        "dim_candidate",
        "dim_org_unit",
        "fact_leave_balance",
        "mart_employee_current",
    }
    leave_q = "Generate a report of employees and leave details for approved leave only"
    assert retrieve_verified_sql(leave_q, grounded_tables=grounded, domain="recruitment") is None

    match = retrieve_verified_sql(
        RECRUITMENT_QUESTION,
        grounded_tables=grounded,
        domain="recruitment",
        min_score=6,
    )
    assert match is not None
    _sql, source, _ = match
    assert source == "verified:recruitment_pipeline_linkedin_referral"


@pytest.mark.parametrize(
    ("question", "tables", "entry_domain", "wrong_domain"),
    [
        (
            "Generate a report of employees and leave details for approved leave only",
            ("fact_leave_balance", "mart_employee_current"),
            "leave",
            "recruitment",
        ),
        (
            RECRUITMENT_QUESTION,
            ("fact_recruitment_pipeline", "dim_candidate", "dim_org_unit"),
            "recruitment",
            "leave",
        ),
    ],
)
def test_verified_domain_guard_blocks_cross_domain(
    question: str,
    tables: tuple[str, ...],
    entry_domain: str,
    wrong_domain: str,
):
    clear_verified_query_cache()
    grounded = set(tables)
    assert (
        retrieve_verified_sql(
            question,
            grounded_tables=grounded,
            domain=wrong_domain,
            min_score=3,
        )
        is None
    )
    assert (
        retrieve_verified_sql(
            question,
            grounded_tables=grounded,
            domain=entry_domain,
            min_score=6,
        )
        is not None
    )
