"""The Legacy SQL Converter is a deliberately-scoped migration helper — unlike
the generic rule-report chat, it IS allowed to know about the data
warehouse's core/meta schema. These tests cover the pure formatting/filtering
steps only (no live datamart connection needed)."""

from app.services.legacy_sql_converter.catalogue import (
    format_code_dictionary_reference, format_core_reference,
    format_dim_value_block, select_dim_value_columns,
)


def test_core_reference_lists_fct_and_dim_tables():
    rows = [
        ("fct_overtime_day", "ot_premium", "Ot Premium"),
        ("fct_overtime_day", "ot_type", "Ot Type"),
        ("dim_holiday_type", "source_id", "Source Id"),
        ("dim_holiday_type", "holiday_type_name", "Holiday Type Name"),
    ]
    ref = format_core_reference(rows)
    assert "core.fct_overtime_day:" in ref
    assert "ot_premium — Ot Premium" in ref
    assert "core.dim_holiday_type:" in ref
    assert "holiday_type_name — Holiday Type Name" in ref


def test_core_reference_uses_curated_label_when_given():
    # format_core_reference doesn't care whether the label came from a
    # curated dictionary view or a naming heuristic — it just renders
    # whatever label it's handed.
    rows = [("dim_holiday_type", "source_id", "Legacy Holiday Type Code")]
    ref = format_core_reference(rows)
    assert "source_id — Legacy Holiday Type Code" in ref


def test_core_reference_skips_partition_shards():
    rows = [
        ("fct_attendance_day", "employee_sk", "Employee Sk"),
        ("fct_attendance_day_default", "employee_sk", "Employee Sk"),
        ("fct_attendance_day_y2026", "employee_sk", "Employee Sk"),
        ("fct_punch_202408", "punch_time", "Punch Time"),
    ]
    ref = format_core_reference(rows)
    assert "core.fct_attendance_day:" in ref
    assert "fct_attendance_day_default" not in ref
    assert "fct_attendance_day_y2026" not in ref
    assert "fct_punch_202408" not in ref


def test_core_reference_skips_non_fct_dim_tables():
    rows = [("br_org_closure", "ancestor_id", "Ancestor Id")]
    assert format_core_reference(rows) == ""


def test_core_reference_empty_rows_yields_empty_reference():
    assert format_core_reference([]) == ""


def test_select_dim_value_columns_drops_audit_and_contact_fields():
    cols = select_dim_value_columns(
        ["holiday_type_sk", "source_id", "holiday_type_name", "_loaded_at",
         "_batch_id", "work_email", "personal_email", "mobile_no", "latitude", "longitude"]
    )
    assert cols == ["holiday_type_sk", "source_id", "holiday_type_name"]


def test_select_dim_value_columns_keeps_booleans_and_rates():
    cols = select_dim_value_columns(["shift_sk", "is_off_shift", "day_ot_rate"])
    assert cols == ["shift_sk", "is_off_shift", "day_ot_rate"]


def test_format_dim_value_block_resolves_legacy_codes():
    rows = [(1, "Poya holiday"), (2, "Mercantile"), (3, "Off Day")]
    block = format_dim_value_block("dim_holiday_type", ["source_id", "holiday_type_name"], rows)
    assert "core.dim_holiday_type (source_id, holiday_type_name):" in block
    assert "1, Poya holiday" in block


def test_format_dim_value_block_drops_all_null_columns():
    rows = [(1, "Colombo", None, None), (2, "Kandy", "value", None)]
    block = format_dim_value_block("dim_branch", ["branch_sk", "branch_name", "branch_name_si", "branch_name_ta"], rows)
    assert "branch_name_ta" not in block
    assert "branch_name_si" in block
    assert "1, Colombo, None" in block


def test_format_dim_value_block_all_null_yields_empty_string():
    assert format_dim_value_block("dim_x", ["only_col"], [(None,), (None,)]) == ""


def test_code_dictionary_reference_groups_by_code_set():
    rows = [
        ("LEAVE_STATUS", 2, "Pending Superior Approval", "PENDING"),
        ("LEAVE_STATUS", 1, "Approved", "APPROVED"),
        ("SHORT_LIEU_LEAVE_STATUS", 2, "Rejected", "REJECTED"),
    ]
    ref = format_code_dictionary_reference(rows)
    assert "LEAVE_STATUS:" in ref
    assert "2 — Pending Superior Approval (PENDING)" in ref
    assert "SHORT_LIEU_LEAVE_STATUS:" in ref
    assert "2 — Rejected (REJECTED)" in ref


def test_code_dictionary_reference_empty_rows_yields_empty_reference():
    assert format_code_dictionary_reference([]) == ""
