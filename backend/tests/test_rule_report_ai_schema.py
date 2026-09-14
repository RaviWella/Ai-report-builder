from app.services.rule_report_ai.schema import build_result_schema


def test_result_schema_has_reply_and_nullable_spec():
    schema = build_result_schema()
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"reply", "spec"}
    assert schema["properties"]["reply"]["type"] == "string"
    any_of_types = {branch.get("type") for branch in schema["properties"]["spec"]["anyOf"]}
    assert "null" in any_of_types
    assert "object" in any_of_types


def test_result_schema_defs_are_hoisted_to_the_root():
    """$ref inside the spec branch (e.g. '#/$defs/RuleCase') resolves against the
    SCHEMA ROOT, not the nested 'spec' property — $defs must live at the top."""
    schema = build_result_schema()
    assert "$defs" in schema
    assert "RuleCase" in schema["$defs"]
    spec_branch = next(b for b in schema["properties"]["spec"]["anyOf"] if b.get("type") == "object")
    assert "$defs" not in spec_branch


def _find_dynamic_maps(node, path=""):
    """Any {"type": "object", "additionalProperties": {...schema...}} node with
    no fixed "properties" — a dynamic-keyed map, which strict structured-output
    enforcement can't reliably satisfy (see schema._relax_dynamic_maps)."""
    found = []
    if isinstance(node, dict):
        if (node.get("type") == "object" and "properties" not in node
                and isinstance(node.get("additionalProperties"), dict)):
            found.append(path)
        for k, v in node.items():
            found += _find_dynamic_maps(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += _find_dynamic_maps(v, f"{path}[{i}]")
    return found


def test_result_schema_has_no_dynamic_key_maps():
    """RuleReportSpec has several dict[str, X] fields (sources, constants,
    rollup, compute, row_cases, column_aliases, define) — real bug: Claude Code's
    structured-output enforcement failed with "Failed to provide valid structured
    output after 5 attempts" against the unmodified schema, because a dynamic
    (open-ended) key space can't be constrained-decoded against. Every such node
    must be relaxed to a free-form object; the real shape is still fully checked
    server-side by spec_validation.validate_spec()."""
    schema = build_result_schema()
    assert _find_dynamic_maps(schema) == []
