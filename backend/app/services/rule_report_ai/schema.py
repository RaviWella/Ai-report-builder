"""The Claude Code `output_format` JSON schema for a rule-chat turn — derived
directly from RuleReportSpec.model_json_schema() so it can never drift from the
actual Pydantic model. Wraps it as {reply, spec, row_number_column, subtotal,
totals, pivot} — spec is null until the AI has enough information to produce
a complete report definition; the other four are presentation-layer config
(never part of RuleReportSpec itself — see PivotSpec's own docstring) the AI
may optionally propose alongside spec, all null/empty by default so a plain
report's turn doesn't need to mention them at all."""

from __future__ import annotations

from app.domain.report_spec import PivotSpec
from app.domain.rule_report import RuleReportSpec


def _relax_dynamic_maps(node: object) -> None:
    """Strict structured-output enforcement can't reliably satisfy a dynamic-keyed
    map — a Pydantic `dict[str, X]` field (sources, constants, rollup, compute,
    row_cases, column_aliases, define) becomes JSON Schema `additionalProperties:
    {schema}`, and constrained decoding has no fixed key set to generate against.
    In practice this makes the model fail structured output entirely ("Failed to
    provide valid structured output after N attempts") rather than produce a
    slightly-wrong object. Loosen those specific nodes to a free-form object —
    the real shape is still fully enforced server-side by
    spec_validation.validate_spec() (Pydantic + a dry compile), with one
    retry-with-the-exact-error turn on failure, so this trades nothing on
    correctness, only on generation reliability. Mutates `node` in place."""
    if isinstance(node, dict):
        additional = node.get("additionalProperties")
        if node.get("type") == "object" and "properties" not in node and isinstance(additional, dict):
            desc = node.get("description")
            node.clear()
            node["type"] = "object"
            if desc:
                node["description"] = desc
            return
        for v in node.values():
            _relax_dynamic_maps(v)
    elif isinstance(node, list):
        for v in node:
            _relax_dynamic_maps(v)


def build_result_schema() -> dict:
    spec_schema = RuleReportSpec.model_json_schema()
    defs = spec_schema.pop("$defs", {})
    _relax_dynamic_maps(defs)
    _relax_dynamic_maps(spec_schema)

    pivot_schema = PivotSpec.model_json_schema()
    defs.update(pivot_schema.pop("$defs", {}))  # PivotSpec is flat today, but stay defensive
    _relax_dynamic_maps(pivot_schema)

    return {
        "type": "object",
        "$defs": defs,
        "properties": {
            "reply": {
                "type": "string",
                "description": "The conversational message to show the analyst — "
                "what you built, or what you still need to know.",
            },
            "spec": {
                "anyOf": [spec_schema, {"type": "null"}],
                "description": "The complete RuleReportSpec, once you have enough "
                "information to produce one. Null while still gathering requirements "
                "or clarifying with the analyst.",
            },
            "row_number_column": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "OPTIONAL presentation config, never part of the "
                "calculation itself. An output column name to number rows 1..N in "
                "(e.g. \"s_no\") — only if the analyst asked for row numbers.",
            },
            "subtotal": {
                "anyOf": [{"type": "object"}, {"type": "null"}],
                "description": "OPTIONAL: {group_by: [...], sum_columns: [...], "
                "label_column, label} — inserts a Total row after each group. Only "
                "propose this if the analyst described grouped subtotals.",
            },
            "totals": {
                "type": "array", "items": {"type": "string"}, "default": [],
                "description": "OPTIONAL: output column names to sum in a final "
                "grand-total row in Excel/PDF. Empty unless the analyst asked for one.",
            },
            "pivot": {
                "anyOf": [pivot_schema, {"type": "null"}],
                "description": "OPTIONAL: reshape a long, one-row-per-(identity, "
                "date/dimension) result into a WIDE grid — one row per identity, one "
                "column per distinct value actually in the result. Propose this ONLY "
                "when the requirement describes one row per identity (e.g. employee) "
                "with a column per date/period (and usually a per-cell status/color) "
                "— see the DSL doc's pivot section for the exact shape and a worked "
                "example. Null for an ordinary one-row-per-record report.",
            },
        },
        "required": ["reply", "spec"],
    }
