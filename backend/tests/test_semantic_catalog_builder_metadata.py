"""metadata_for_builder() — the human field-picker projection (never the AI's).

Distinct from metadata_for_ai(): surfaces sample values (except for `pii`
fields) and an `is_anchor` flag so a label that repeats across entities
(e.g. "Designation" on both Employee and a historical mart) is disambiguated
in the picker without needing AI.
"""

from __future__ import annotations

from app.domain.enums import FieldRole, FieldType
from app.domain.semantic import Entity, PhysicalColumn, SemanticCatalog, SemanticField


def _field(ref: str, label: str, **kw) -> SemanticField:
    entity_key, col = ref.split(".", 1)
    return SemanticField(
        ref=ref, label=label, type=FieldType.STRING, role=FieldRole.DIMENSION,
        physical=PhysicalColumn(table=f"mart_{entity_key}", column=col),
        **kw,
    )


def _entity(key: str, name: str, fields: list[SemanticField]) -> Entity:
    return Entity(
        name=name, key=key, base_schema="mart", base_table=f"mart_{key}",
        primary_key=f"{key}_sk", fields=fields,
    )


def _catalog() -> SemanticCatalog:
    employee = _entity("employee", "Employee", [
        _field("employee.designation", "Designation"),
        _field("employee.nic_no", "NIC Number", pii=True, sample_values=["912345678V"]),
    ])
    promotion = _entity("promotion_history", "Promotion History", [
        _field("promotion_history.designation", "Designation",
               description="The title held immediately before this promotion",
               sample_values=["Junior Analyst", "Analyst", "Senior Analyst"]),
    ])
    return SemanticCatalog(tenant_id="t", version=1, entities=[employee, promotion])


def test_anchor_entity_is_flagged():
    fields = {f["ref"]: f for f in _catalog().metadata_for_builder()}
    assert fields["employee.designation"]["is_anchor"] is True
    assert fields["promotion_history.designation"]["is_anchor"] is False


def test_blank_description_gets_synthesized_fallback():
    fields = {f["ref"]: f for f in _catalog().metadata_for_builder()}
    assert fields["employee.designation"]["description"] == "Employee's Designation"


def test_real_description_is_left_untouched():
    fields = {f["ref"]: f for f in _catalog().metadata_for_builder()}
    assert fields["promotion_history.designation"]["description"] == (
        "The title held immediately before this promotion"
    )


def test_sample_values_included_when_present():
    fields = {f["ref"]: f for f in _catalog().metadata_for_builder()}
    assert fields["promotion_history.designation"]["sample_values"] == [
        "Junior Analyst", "Analyst", "Senior Analyst",
    ]


def test_pii_field_never_returns_sample_values():
    fields = {f["ref"]: f for f in _catalog().metadata_for_builder()}
    assert fields["employee.nic_no"]["sample_values"] == []


def test_metadata_for_ai_is_unaffected():
    """The AI-facing projection must not gain sample_values/is_anchor — this is
    the one thing that must NEVER change as part of adding the builder shape."""
    ai_fields = {f["ref"]: f for f in _catalog().metadata_for_ai()}
    assert "sample_values" not in ai_fields["promotion_history.designation"]
    assert "is_anchor" not in ai_fields["promotion_history.designation"]
    assert "is_record_key" not in ai_fields["promotion_history.designation"]


def test_record_identity_ref_is_the_catalogue_field_not_a_hardcoded_name():
    """Identity is the anchor entity's business-number column, exposed as
    whatever ref THIS catalogue assigned — not a guessed employee.emp_no."""
    staff = _entity("workforce", "Workforce", [
        SemanticField(
            ref="workforce.badge", label="Staff Badge",
            type=FieldType.STRING, role=FieldRole.DIMENSION,
            physical=PhysicalColumn(table="mart_workforce", column="employee_no"),
        ),
        _field("workforce.branch", "Branch"),
    ])
    catalog = SemanticCatalog(tenant_id="t", version=1, entities=[staff])
    assert catalog.record_identity_ref() == "workforce.badge"
    flags = {f["ref"]: f["is_record_key"] for f in catalog.metadata_for_builder()}
    assert flags["workforce.badge"] is True
    assert flags["workforce.branch"] is False
