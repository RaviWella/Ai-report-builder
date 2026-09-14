"""
Fast CI: every question-bank entry with a template must produce catalog SQL (no warehouse).
"""
from pathlib import Path

import yaml

from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.domain_sql.report_spec import compile_report_spec
from app.services.ai_services.datamart.validation.report_spec_validate import validate_sql_against_report_spec
from app.services.ai_services.datamart.domain_sql.report_sql_router import try_build_sql_from_report_spec
from app.services.ai_services.datamart.schema_broker import SchemaGrounding

BANK_PATH = Path(__file__).resolve().parents[2] / "tools" / "datamart_question_bank.yaml"

_GROUNDING_BY_SECTION: dict[str, SchemaGrounding] = {
    "payroll": SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_payroll_summary": [
                "employee_id",
                "emp_fullname",
                "branch",
                "payroll_group_name",
                "basic_salary",
            ],
            "hr.dim_payroll_group": [
                "payroll_group_name",
                "payroll_frequency",
                "currency_code",
            ],
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "location_name",
                "payroll_group",
                "basic_salary",
            ],
        },
        source="test",
    ),
    "leave": SchemaGrounding(
        columns_by_table={
            "hr.fact_leave_balance": [
                "source_emp_id",
                "leave_type_name",
                "period_label",
                "days_approved",
            ],
            "hr.mart_employee_current": [
                "emp_no",
                "emp_fullname",
                "location_name",
            ],
            "hr_semantic.vw_leave_summary": [
                "employee_id",
                "leave_type_name",
                "days_taken",
            ],
        },
        source="test",
    ),
    "attendance": SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_attendance_summary": [
                "period_label",
                "present_days",
                "absent_days",
                "late_events",
            ],
        },
        source="test",
    ),
    "workforce": SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_fullname",
                "emp_no",
                "legal_entity",
                "location_name",
                "designation_department",
                "emp_position",
                "superior_emp_no",
                "superior_fullname",
            ],
        },
        source="test",
    ),
    "attrition": SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_turnover": ["department_id", "employee_id"],
            "hr_semantic.vw_headcount": [
                "department_id",
                "employee_id",
                "is_active",
            ],
            "hr.mart_employee_current": ["designation_department"],
        },
        source="test",
    ),
    "compensation": SchemaGrounding(
        columns_by_table={
            "hr.mart_employee_current": [
                "emp_fullname",
                "emp_no",
                "basic_salary",
                "designation_department",
            ],
            "hr.dim_employee": ["employee_id", "emp_fullname"],
            "hr_semantic.vw_payroll_summary": [
                "emp_fullname",
                "basic_salary",
                "net_salary",
            ],
            "hr_semantic.vw_salary_bands": [
                "band_min",
                "band_max",
                "basic_salary",
            ],
        },
        source="test",
    ),
    "headcount": SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_headcount": ["employee_id", "is_active"],
            "hr.mart_employee_current": ["emp_fullname", "location_name"],
            "hr.mart_headcount_monthly": ["period_month", "headcount"],
        },
        source="test",
    ),
    "performance": SchemaGrounding(
        columns_by_table={
            "hr_semantic.vw_performance_summary": [
                "department",
                "rating",
                "review_cycle",
            ],
            "hr.mart_employee_current": ["designation_department"],
        },
        source="test",
    ),
    "recruitment": SchemaGrounding(
        columns_by_table={
            "hr.fact_recruitment_pipeline": [
                "candidate_id",
                "recruitment_source",
                "appointment_date",
                "expected_joining_date",
            ],
            "hr.dim_candidate": ["candidate_name", "email"],
            "hr.dim_org_unit": ["org_unit_name"],
        },
        source="test",
    ),
}


def _grounding_for_case(section: str, entry: dict) -> SchemaGrounding | None:
    domain = (entry.get("eval_domain") or section).lower()
    for key, grounding in _GROUNDING_BY_SECTION.items():
        if key in domain or domain in key:
            return grounding
    return _GROUNDING_BY_SECTION.get(section)


def _template_cases():
    raw = yaml.safe_load(BANK_PATH.read_text(encoding="utf-8"))
    cases = []
    for section, entries in raw.items():
        if section == "meta" or not isinstance(entries, list):
            continue
        for entry in entries:
            tpl = entry.get("template")
            if tpl:
                cases.append((section, entry, entry["question"].strip(), tpl))
    return cases


def test_question_bank_catalog_templates_produce_sql():
    failures = []
    for section, entry, question, expected_tpl in _template_cases():
        g = _grounding_for_case(section, entry)
        if not g:
            failures.append(f"{section}: no test grounding fixture")
            continue
        spec = compile_report_spec(question, chat_intent=ChatIntent.NEW_QUERY)
        if spec.template_id != expected_tpl:
            failures.append(
                f"{section}: template_id {spec.template_id!r} != {expected_tpl!r}"
            )
            continue
        routed = try_build_sql_from_report_spec(question, spec, grounding=g)
        if not routed:
            failures.append(f"{section}: router returned None for {question[:40]!r}")
            continue
        sql, _tag = routed
        err = validate_sql_against_report_spec(question, sql, spec)
        if err:
            failures.append(f"{section}: spec validate: {err}")
    assert not failures, failures
