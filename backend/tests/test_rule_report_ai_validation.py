"""validate_spec() is the "never trust the AI's raw JSON" gate — structural
(Pydantic) AND a dry compile, before a spec is ever shown as ready."""

import json
from pathlib import Path

from app.services.rule_report_ai.spec_validation import validate_spec

_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "app/services/rule_report_ai/examples"


def _load(name: str) -> dict:
    return json.loads((_EXAMPLES_DIR / name).read_text())


def test_a_real_working_spec_validates_clean():
    raw = _load("02_meal_plan_allowance_time_functions.json")
    spec, error = validate_spec(raw)
    assert error is None
    assert spec is not None
    assert spec.name == "meal_plan_allowance"


def test_multi_source_join_spec_validates_clean():
    raw = _load("01_golden_key_ot_multi_source_join.json")
    spec, error = validate_spec(raw)
    assert error is None
    assert spec is not None


def test_missing_required_field_is_rejected_with_a_clear_message():
    raw = _load("02_meal_plan_allowance_time_functions.json")
    del raw["grain"]
    spec, error = validate_spec(raw)
    assert spec is None
    assert "grain" in error


def test_output_column_not_produced_by_the_spec_is_caught_by_the_dry_compile():
    """Pydantic alone wouldn't catch this — it's a compiler-level guard."""
    raw = _load("02_meal_plan_allowance_time_functions.json")
    raw["output"] = [*raw["output"], "not_a_real_column"]
    spec, error = validate_spec(raw)
    assert spec is None
    assert "not_a_real_column" in error


def test_expression_outside_the_whitelist_is_rejected():
    raw = _load("02_meal_plan_allowance_time_functions.json")
    raw["compute"]["hacked"] = "__import__('os')"
    spec, error = validate_spec(raw)
    assert spec is None
    assert error
