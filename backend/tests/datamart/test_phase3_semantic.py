"""Phase 3 semantic layer tests (no warehouse)."""
from app.services.ai_services.datamart.semantic.semantic_layer import (
    catalog_join_hints_for_tables,
    clear_catalog_cache,
    resolve_semantics,
)


def setup_function() -> None:
    clear_catalog_cache()


def test_employee_information_resolution_seeds_employee_table():
    r = resolve_semantics(
        "Generate a workforce report with employee name, company, branch, and department"
    )
    assert "dim_employee" in r.seed_tables
    assert "employee_information" in r.topics_matched
    assert "employee_name" in r.dimensions_matched or "company" in r.dimensions_matched
    assert "SEMANTIC GUIDANCE" in r.prompt_block
    assert "legal_entity" in r.prompt_block or "full_name" in r.prompt_block


def test_payroll_topic_adds_payroll_fact():
    r = resolve_semantics("Show top 10 highest paid employees by basic salary")
    assert "payroll" in r.topics_matched or "top_paid" in r.metrics_matched
    assert "fact_payroll_detail" in r.seed_tables


def test_reporting_manager_dimension():
    r = resolve_semantics(
        "List employees with reporting manager employee id and designation"
    )
    assert "reporting_manager" in r.dimensions_matched or "designation" in r.dimensions_matched
    assert "manager_employee_id" in r.prompt_block


def test_catalog_join_hints_when_both_tables():
    hints = catalog_join_hints_for_tables(["dim_employee", "fact_payroll_detail"])
    assert any("fact_payroll_detail" in h for h in hints)
    assert any("employee" in h for h in hints)


def test_leave_utilization_seeds_leave_mart_tables():
    r = resolve_semantics(
        "Prepare a leave utilization report combining leave transaction, leave type, "
        "and employee information with employee name, branch, and leave days taken"
    )
    assert "leave" in r.topics_matched
    assert "fact_leave_transaction" in r.seed_tables
    assert "dim_leave_type" in r.seed_tables
    assert "dim_employee" in r.seed_tables
    assert "full_name" in r.prompt_block or "employee_name" in r.dimensions_matched


def test_recruitment_topic_seeds_pipeline():
    r = resolve_semantics("What is our average time to hire by recruitment pipeline stage?")
    assert "recruitment" in r.topics_matched
    assert "fact_recruitment_pipeline" in r.seed_tables


def test_loan_topic_keywords_without_tables():
    r = resolve_semantics("Show staff loan balances and repayment schedule")
    assert "loan" in r.topics_matched


def test_employee_information_maps_name_and_branch():
    r = resolve_semantics(
        "Generate a workforce report with employee name, employee ID, company, branch, department"
    )
    assert "dim_employee" in r.seed_tables
    assert "full_name" in r.prompt_block
    assert "branch" in r.prompt_block
