"""WS-3 — validation framework: validators are SELECT-only; summary/serve-policy."""

from __future__ import annotations

from app.query_engine import guards
from app.services.validation_service import VALIDATORS, ValidationResult, _summary

_CATEGORIES = {"balance", "referential", "completeness", "uniqueness", "period", "freshness"}


def test_validators_are_select_only_and_well_formed():
    assert VALIDATORS, "at least one validator"
    for v in VALIDATORS:
        assert v.severity in ("error", "warning", "info")
        assert v.category in _CATEGORIES
        guards.assert_select_only(v.sql)  # no write/DDL can hide in a check


def test_summary_flags_critical_only_on_failing_error_severity():
    fail_err = ValidationResult("x", "uniqueness", "error", "fail", 2, "")
    fail_warn = ValidationResult("y", "balance", "warning", "fail", 2, "")
    assert _summary([fail_warn])["critical_failure"] is False
    assert _summary([fail_err])["critical_failure"] is True


def test_summary_counts():
    results = [
        ValidationResult("a", "balance", "warning", "pass", 0, ""),
        ValidationResult("b", "uniqueness", "error", "fail", 3, ""),
        ValidationResult("c", "referential", "warning", "error", None, ""),
    ]
    assert _summary(results) == {
        "checks": 3, "passed": 1, "failed": 1, "errored": 1, "critical_failure": True,
    }
