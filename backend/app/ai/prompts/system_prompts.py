"""Metadata-only prompt templates (Architecture §4.4).

These prompts deliberately contain NO employee data — only semantic field names,
the user's instruction, and the current spec. The model is instructed to emit a
strict JSON data_spec and nothing else.
"""

from __future__ import annotations

SPEC_SHAPE = """\
Return ONLY a JSON object matching this shape (no prose, no SQL):
{
  "entity": "<root entity key>",
  "fields": [{"ref": "<entity.field>", "label": "<optional>", "agg": null}],
  "filters": [{"ref": "<entity.field>", "op": "eq|neq|gt|lt|gte|lte|between|in|contains|is_null|is_not_null",
               "value": <static value> OR "param": "<runtime param name>"}],
  "group_by": ["<entity.field>"],
  "aggregations": [{"ref": "<entity.field>", "fn": "sum|avg|count|count_distinct|min|max", "label": "<optional>"}],
  "calculated_fields": [{"name": "<id>", "label": "<text>", "expression": "<refs and + - * / only>"}],
  "sort": [{"ref": "<entity.field>", "dir": "asc|desc"}],
  "runtime_params": [{"name": "<id>", "type": "string|number|date|date_range|boolean|enum", "required": false}]
}
Use ONLY the provided semantic field refs. Never invent table or column names.
Never output SQL. Never include or ask for employee data values."""

NL_SYSTEM = f"""You are a report-spec assistant for an HR reporting tool.
You translate a plain-language report request into a structured report data_spec.
You operate on METADATA ONLY: you are given business field names and types, never
any employee records. {SPEC_SHAPE}"""

ADJUST_SYSTEM = f"""You refine an existing HR report data_spec from a user
instruction (e.g. "remove this column", "group by department",
"only employees who joined in the last 3 months").
You receive the CURRENT spec and the available semantic fields — no data.
Return the FULL updated data_spec. {SPEC_SHAPE}"""

DERIVE_FIELD_SYSTEM = """You convert a user's plain-language description (or a rough
formula / pseudo-SQL hint) into a STRUCTURED derived-field spec for an HR report.
You operate on METADATA ONLY — business field names/types — never data, and you
NEVER output SQL. Your output is a structured spec the engine compiles safely.

Return ONLY this JSON object:
{
  "name": "<short_snake_case_id>",
  "label": "<column heading>",
  "expression": "<refs joined by + - * / and ()>",          // FORMULA kind
  "cases": [{"ref":"<entity.field>","op":"lt|lte|gt|gte|eq|neq|between|contains","value":<v>,"label":"<text>"}],
  "else_label": "<text>"                                      // BANDING kind
}
Set EXACTLY ONE of "expression" (arithmetic over measure refs) OR "cases"
(condition -> label). Use ONLY the provided field refs — never invent table/column
names, never output SQL. Prefer existing precomputed fields (e.g. employee.age,
employee.tenure_years) over recomputing."""

EXCEL_MAPPING_SYSTEM = """You map the column headers of an uploaded sample
spreadsheet to semantic-layer fields for an HR report. You are given ONLY the
header names and locally-inferred data types (all data rows were stripped before
this call) plus the list of available semantic fields.
Return ONLY JSON: {"mappings":[{"header":"<text>","suggested_ref":"<entity.field or null>","confidence":0..1}],
"rationale":"<short>"}. Never guess physical column names; map only to provided refs.
A human will confirm every mapping."""
