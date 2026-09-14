"""format_catalogue_reference() grounds the rule-chat prompt in the tenant's
REAL physical schema — without it, the AI invents plausible-but-wrong column
names. Deliberately sourced ONLY from the curated SemanticService catalogue —
Report Builder is a generic platform and must not hardcode knowledge of any
one data warehouse's internal schema layout (see catalogue.py docstring)."""

from app.domain.semantic import Entity, PhysicalColumn, SemanticCatalog, SemanticField
from app.domain.enums import FieldRole, FieldType
from app.services.rule_report_ai.catalogue import format_catalogue_reference


def _field(ref: str, label: str, table: str, column: str, schema: str | None = None) -> SemanticField:
    return SemanticField(
        ref=ref, label=label, type=FieldType.STRING, role=FieldRole.DIMENSION,
        physical=PhysicalColumn(table=table, column=column, schema_name=schema),
    )


def _catalog(entities: list[Entity]) -> SemanticCatalog:
    return SemanticCatalog(tenant_id="t1", version=1, entities=entities)


def test_lists_every_table_and_column_grouped():
    catalog = _catalog([
        Entity(
            name="Attendance", key="attendance", base_schema="mart", base_table="mart_attendance_daily",
            primary_key="employee_sk",
            fields=[
                _field("attendance.employee_no", "Employee Number", "mart_attendance_daily", "employee_no"),
                _field("attendance.work_date", "Work Date", "mart_attendance_daily", "work_date"),
            ],
        ),
    ])
    ref = format_catalogue_reference(catalog)
    assert "mart.mart_attendance_daily:" in ref
    assert "employee_no — Employee Number" in ref
    assert "work_date — Work Date" in ref


def test_field_level_schema_name_overrides_entity_base_schema():
    catalog = _catalog([
        Entity(
            name="Overtime", key="overtime", base_schema="mart", base_table="mart_attendance_daily",
            primary_key="employee_sk",
            fields=[_field("overtime.ot_premium", "OT Premium", "fct_overtime_day", "ot_premium", schema="core")],
        ),
    ])
    ref = format_catalogue_reference(catalog)
    assert "core.fct_overtime_day:" in ref
    assert "mart.fct_overtime_day:" not in ref


def test_empty_catalog_yields_empty_reference():
    assert format_catalogue_reference(_catalog([])) == ""


def test_duplicate_physical_column_across_entities_is_deduped():
    fields_a = [_field("a.branch", "Branch", "mart_attendance_daily", "branch")]
    fields_b = [_field("b.branch", "Branch (payroll)", "mart_attendance_daily", "branch")]
    catalog = _catalog([
        Entity(name="A", key="a", base_schema="mart", base_table="mart_attendance_daily",
               primary_key="pk", fields=fields_a),
        Entity(name="B", key="b", base_schema="mart", base_table="mart_attendance_daily",
               primary_key="pk", fields=fields_b),
    ])
    ref = format_catalogue_reference(catalog)
    assert ref.count("mart.mart_attendance_daily:") == 1
    assert ref.count("branch —") == 1
