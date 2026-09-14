"""Never trust the AI's raw JSON (same principle as AIService's DataSpec path):
validate structurally (Pydantic) AND compile it (a dry run, never executed)
before a `spec` is ever shown to the analyst as "ready"."""

from __future__ import annotations

from pydantic import ValidationError

from app.domain.rule_report import RuleReportSpec
from app.query_engine.rule_compiler import compile_rule_report


def validate_spec(raw_spec: dict) -> tuple[RuleReportSpec | None, str | None]:
    """Returns (spec, None) if raw_spec is a well-formed, compilable
    RuleReportSpec, else (None, error_message)."""
    try:
        spec = RuleReportSpec.model_validate(raw_spec)
    except ValidationError as exc:
        return None, exc.errors()[0]["msg"]
    try:
        # A dummy value per declared filter so column/type-dependent expressions
        # (e.g. an `expose_as` projection) compile cleanly — this never runs
        # against a real database.
        dummy_params = {f.name: _dummy_value(f.type) for f in spec.filters}
        compile_rule_report(spec, dummy_params)
    except (ValueError, KeyError) as exc:
        # KeyError: a join/priority/tiebreak references a column not declared in
        # that source's `columns` list — a plausible AI mistake, not a bug here.
        return None, str(exc) if isinstance(exc, ValueError) else f"unknown column: {exc}"
    return spec, None


def _dummy_value(ftype: str):
    if ftype == "date":
        return "2000-01-01"
    if ftype == "number":
        return 0
    return "x"
