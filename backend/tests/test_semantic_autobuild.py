"""Unit tests for the auto-introspection engine's pure logic (DB-free): label
normalisation, measure/dimension classification, PII heuristic, and entity-key
derivation. These lock the generic rules that turn physical `hr` mart/dim columns
into a governed catalogue — no hand-listed fields, no hr_semantic.
"""

from unittest.mock import MagicMock, patch

from app.services.semantic_autobuild import (
    _entity_key, _is_measure, _is_pii, _json_key_fields, _label, _safe_key_fragment,
)


def test_label_expands_abbrev_and_acronyms():
    assert _label("emp_no") == "Employee No"
    assert _label("epf_no") == "EPF No"
    assert _label("emp_fullname") == "Employee Full Name"
    assert _label("date_of_birth") == "Date of Birth"
    assert _label("attendance_rate_pct") == "Attendance Rate %"
    assert _label("nic") == "NIC"


def test_measure_only_for_numeric_measure_like_columns():
    assert _is_measure("days_present", "bigint")
    assert _is_measure("total_overtime_hours", "numeric")
    assert _is_measure("attendance_rate_pct", "numeric")
    # money/amount columns without an "amount" hint are still measures
    assert _is_measure("basic_salary", "numeric")
    assert _is_measure("net_salary", "numeric")
    assert _is_measure("loan_deduction", "numeric")
    assert _is_measure("service_charge", "numeric")
    # numerics that are NOT measures (identifiers / periods)
    assert not _is_measure("year", "smallint")
    assert not _is_measure("payroll_year", "smallint")
    assert not _is_measure("day_of_week", "integer")
    assert not _is_measure("employee_id", "integer")
    assert not _is_measure("source_shift_id", "integer")
    assert not _is_measure("shift_sk", "text")
    # non-numeric never a measure
    assert not _is_measure("department", "character varying")


def test_pii_heuristic_flags_sensitive_names():
    assert _is_pii("emp_fullname")
    assert _is_pii("nic")
    assert _is_pii("basic_salary")
    assert _is_pii("personal_email")
    assert not _is_pii("department")
    assert not _is_pii("days_present")


def test_entity_key_strips_prefix():
    assert _entity_key("mart_attendance_monthly_summary") == "attendance_monthly_summary"
    assert _entity_key("dim_shift") == "shift"
    assert _entity_key("fact_attendance") == "fact_attendance"  # non mart/dim unchanged


def test_safe_key_fragment_sanitizes_arbitrary_json_keys():
    assert _safe_key_fragment("Probation Notes") == "probation_notes"
    assert _safe_key_fragment("visa-expiry!") == "visa_expiry"
    assert _safe_key_fragment("   ") == "field"  # nothing left after sanitizing


def _mock_engine(rows: list[tuple]) -> MagicMock:
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.execute.return_value.fetchall.return_value = rows
    eng = MagicMock()
    eng.connect.return_value = conn
    return eng


def test_json_key_fields_builds_one_field_per_discovered_key():
    """A JSON/JSONB "extra fields" blob isn't exposed as one opaque field — every
    key found in the data becomes its own field, bound via json_key (compiled to
    `column ->> 'key'` by the query engine, see sql_builder.col_for)."""
    eng = _mock_engine([("probation_notes",), ("visa_expiry",)])
    with patch("app.services.semantic_autobuild.get_datamart_engine", return_value=eng):
        fields = _json_key_fields("dm", "mart_employment", "employment", "extra_fields")

    assert [f.ref for f in fields] == [
        "employment.extra_fields__probation_notes",
        "employment.extra_fields__visa_expiry",
    ]
    assert fields[0].label == "Probation Notes"
    assert fields[0].physical.table == "mart_employment"
    assert fields[0].physical.column == "extra_fields"
    assert fields[0].physical.json_key == "probation_notes"
    assert fields[0].type.value == "string"
    assert fields[0].role.value == "dimension"


def test_json_keys_checks_object_type_before_calling_jsonb_object_keys():
    """jsonb_object_keys() raises for a non-object JSON value (an array, a bare
    scalar) — the object-type check must happen in the SAME subquery, before
    the LATERAL join ever calls it on that row, not as an outer filter applied
    after (which would be too late to stop the error)."""
    eng = _mock_engine([])
    with patch("app.services.semantic_autobuild.get_datamart_engine", return_value=eng):
        _json_key_fields("dm", "mart_employment", "employment", "extra_fields")

    sql = str(eng.connect.return_value.execute.call_args_list[-1].args[0])
    typeof_pos = sql.index("jsonb_typeof")
    lateral_pos = sql.index("LATERAL jsonb_object_keys")
    assert typeof_pos < lateral_pos


def test_json_key_fields_degrades_to_empty_on_query_failure():
    """Best-effort: a malformed blob or unsupported JSON shape must never fail
    the whole catalogue rebuild — just yields no fields for that one column."""
    eng = MagicMock()
    eng.connect.side_effect = RuntimeError("boom")
    with patch("app.services.semantic_autobuild.get_datamart_engine", return_value=eng):
        assert _json_key_fields("dm", "mart_x", "x", "blob") == []
