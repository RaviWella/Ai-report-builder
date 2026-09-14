"""Workforce report retrieval must not require vw_payroll_summary."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.validation.retrieval_validator import validate_retrieval
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.orchestration.schema_linker import build_schema_links
from app.services.ai_services.datamart.semantic.semantic_layer import clear_catalog_cache, resolve_semantics
from app.services.ai_services.datamart.validation.validation_models import ValidationStatus

WORKFORCE_Q = (
    "Generate a workforce report by combining employee and organization data. "
    "Include employee name, employee ID, company, branch, department, "
    "organization unit, designation ID, and reporting manager employee ID"
)


def setup_function() -> None:
    clear_catalog_cache()


def test_workforce_report_not_blocked_without_payroll_summary_view():
    semantics = resolve_semantics(WORKFORCE_Q)
    grounding = SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_fullname",
                "employee_sk",
                "legal_entity",
                "branch_name",
            ],
            "hr.dim_employee": ["employee_id", "employee_sk", "designation_id", "org_unit_sk"],
            "hr.dim_designation": ["designation_sk", "department_id"],
            "hr.dim_org_unit": ["org_unit_name"],
        },
        source="test",
    )
    links = build_schema_links(WORKFORCE_Q, semantics, grounding)
    result = validate_retrieval(
        question=WORKFORCE_Q,
        grounding=grounding,
        semantics=semantics,
        schema_links=links,
        chat_intent=ChatIntent.NEW_QUERY,
    )
    assert "vw_payroll_summary" not in result.missing_tables
    assert result.status != ValidationStatus.INSUFFICIENT
