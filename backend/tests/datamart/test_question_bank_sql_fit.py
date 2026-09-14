"""
Question bank: every prompt must resolve governed SQL that fits the question.

Offline eval (no LLM, no warehouse) — run full bank:
  cd backend && PYTHONPATH=. pytest tests/datamart/test_question_bank_sql_fit.py -v

CLI with SQL output:
  PYTHONPATH=. python tools/run_question_bank_sql_fit.py --show-sql --json tools/question_bank_sql_fit.json
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.pipeline.question_bank_sql_fit import (
    eval_question_bank_sql_fit,
    evaluate_sql_fit_one,
)

BANK_PATH = Path(__file__).resolve().parents[2] / "tools" / "datamart_question_bank.yaml"

# Minimum share of bank questions that must pass full fit checks in CI.
MIN_FIT_PASS_RATE = 0.85


@pytest.fixture(scope="module")
def bank_cases():
    _raw, cases = load_question_bank(BANK_PATH)
    return cases


@pytest.fixture(scope="module")
def fit_report(bank_cases):
    return eval_question_bank_sql_fit(bank_cases, mode="offline")


def test_question_bank_resolves_sql_for_all_cases(fit_report):
    assert fit_report.unresolved == 0, (
        f"{fit_report.unresolved} questions had no Tier A/B SQL"
    )
    assert fit_report.with_sql == fit_report.total


def test_question_bank_sql_syntax_valid(fit_report):
    bad = [r for r in fit_report.results if r.has_sql and not r.syntax_ok]
    assert not bad, [(r.section, r.syntax_error) for r in bad[:5]]


def test_question_bank_sql_fit_pass_rate(fit_report):
    rate = fit_report.passed / fit_report.total if fit_report.total else 0
    assert rate >= MIN_FIT_PASS_RATE, (
        f"fit pass rate {rate:.1%} below {MIN_FIT_PASS_RATE:.0%}; "
        f"failed={fit_report.failed}"
    )


def test_employee_bank_sql_fit_from_verified_yaml():
    """Bank has no exact bank-details row — spot-check via fit eval case."""
    q = (
        "List employee number, employee full name, employment category "
        "and bank details of the employees"
    )
    case = {
        "section": "spot_check",
        "question": q,
        "expect_tables": [
            "mart_employee_current",
            "fct_salary_bank_instruction",
            "dim_bank",
        ],
        "eval_domain": "workforce",
    }
    r = evaluate_sql_fit_one(case, mode="offline")
    assert r.has_sql, r.errors
    sql_l = (r.sql or "").lower()
    assert "mart_employee_current" in sql_l
    assert "bank" in sql_l or "fct_salary_bank" in sql_l


def test_shift_sql_fit_spot_check():
    """Shift list is not in the bank — verify governed template + fit checks."""
    from app.services.ai_services.datamart.schema_broker import SchemaGrounding

    q = "List employee no, employee name and assigned shift name"
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": ["emp_no", "emp_fullname", "shift_id"],
            "hr.dim_shift": ["source_shift_id", "shift_name"],
        },
        source="test",
    )
    r = evaluate_sql_fit_one(
        {
            "section": "spot_check",
            "question": q,
            "expect_tables": ["mart_employee_current", "dim_shift"],
            "eval_domain": "workforce",
        },
        mode="offline",
    )
    assert r.has_sql, r.errors
    assert r.tier in ("A", "B")
    sql_l = (r.sql or "").lower()
    assert "shift" in sql_l
    assert "source_shift_id" in sql_l or "dim_shift" in sql_l


def test_run_question_bank_sql_fit_cli_exits_zero():
    from tools.run_question_bank_sql_fit import main

    assert main([]) == 0
