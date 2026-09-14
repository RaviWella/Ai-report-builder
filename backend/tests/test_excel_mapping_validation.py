"""validate_mapping must reject anything the AI wasn't allowed to say: a
header outside the given "headers to map" list (e.g. one already mapped,
or hallucinated), or a ref that doesn't exist in the tenant's real
catalogue — same never-trust-raw-JSON principle as rule_report_ai's
spec_validation, no live database needed."""

from __future__ import annotations

from app.domain.enums import FieldRole, FieldType
from app.domain.semantic import Entity, PhysicalColumn, SemanticCatalog, SemanticField
from app.services.excel_mapping_ai.mapping_validation import validate_mapping


def _catalog() -> SemanticCatalog:
    field = SemanticField(
        ref="employee.emp_no", label="Employee No", type=FieldType.STRING, role=FieldRole.DIMENSION,
        physical=PhysicalColumn(table="dim_employee", column="emp_no"),
    )
    entity = Entity(
        name="Employee", key="employee", base_schema="mart", base_table="dim_employee",
        primary_key="employee_sk", fields=[field],
    )
    return SemanticCatalog(tenant_id="t", version=1, entities=[entity])


def test_a_valid_mapping_passes():
    mapping, error = validate_mapping(
        _catalog(), ["Emp No"], [{"header": "Emp No", "ref": "employee.emp_no"}],
    )
    assert error is None
    assert mapping == {"Emp No": "employee.emp_no"}


def test_null_ref_means_skip_the_column():
    mapping, error = validate_mapping(_catalog(), ["Spacer"], [{"header": "Spacer", "ref": None}])
    assert error is None
    assert mapping == {"Spacer": None}


def test_a_header_outside_the_allowed_list_is_rejected():
    mapping, error = validate_mapping(
        _catalog(), ["Emp No"], [{"header": "Gross Pay", "ref": "employee.emp_no"}],
    )
    assert mapping is None
    assert "Gross Pay" in error


def test_an_unknown_ref_is_rejected():
    mapping, error = validate_mapping(
        _catalog(), ["Emp No"], [{"header": "Emp No", "ref": "payroll.made_up_field"}],
    )
    assert mapping is None
    assert "made_up_field" in error


def test_no_mappings_at_all_is_not_an_error():
    # The AI asking a clarifying question instead of proposing anything.
    mapping, error = validate_mapping(_catalog(), ["Emp No"], None)
    assert mapping is None
    assert error is None
