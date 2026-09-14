"""
Offline datamart eval — ReportSpec golden SQL + broker retrieval (no LLM, no warehouse).

Usage (from backend/):
  PYTHONPATH=. python tools/run_datamart_eval.py

CI: tests/datamart/test_datamart_eval_ci.py (mocked broker; golden SQL always runs).
"""
from __future__ import annotations

import json
import sys
from typing import Any, Optional

from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent, classify_chat_intent
from app.services.ai_services.datamart.domain_sql.report_spec import ReportDomain, compile_report_spec
from app.services.ai_services.datamart.validation.report_spec_validate import validate_sql_against_report_spec
from app.services.ai_services.datamart.domain_sql.leave_report_sql import try_build_leave_detail_report_sql
from app.services.ai_services.datamart.domain_sql.report_sql_router import try_build_sql_from_report_spec
from app.services.ai_services.datamart.schema_broker import (
    BrokerMode,
    SchemaGrounding,
    build_schema_grounding,
    ensure_grounding_includes_tables,
)
from app.services.ai_services.datamart.orchestration.schema_linker import build_schema_links
from app.services.ai_services.datamart.semantic.semantic_layer import resolve_semantics
from app.services.ai_services.datamart.validation.retrieval_validator import validate_retrieval
from app.services.ai_services.datamart.domain_sql.workforce_sql_template import try_build_workforce_report_sql

# ── Golden questions (CI regression: leave / attrition / attendance / workforce) ──

LEAVE_GOLDEN_Q = (
    "Generate a report of employees and their leave details by combining employee "
    "and leave transaction information. Include employee name, employee ID, branch, "
    "leave type, leave start date, leave end date, total leave days, and leave status. "
    "Display only approved leave requests"
)

ATTRITION_GOLDEN_Q = "Which departments have the highest attrition rate?"

ATTENDANCE_GOLDEN_Q = "Show attendance summary for this month"

WORKFORCE_GOLDEN_Q = (
    "Generate a workforce report by combining employee and organization data. "
    "Include employee name, employee ID, company, branch, department, "
    "organization unit, designation ID, and reporting manager employee ID"
)

PAYROLL_GOLDEN_Q = (
    "Prepare a payroll summary report by combining employee, payroll group, and "
    "employee snapshot details. Include employee name, employee ID, payroll group "
    "name, pay frequency, currency code, branch, and current basic salary."
)

WORKFORCE_MART_ONLY_SQL = """
SELECT m.emp_fullname AS employee_name, m.emp_no AS employee_no
FROM hr.mart_employee_current m
LIMIT 500
"""

GOLDEN_REPORT_CASES: list[dict[str, Any]] = [
    {
        "id": "golden_leave_detail",
        "question": LEAVE_GOLDEN_Q,
        "expect_domain": ReportDomain.LEAVE.value,
        "expect_template": "leave.detail_list",
        "sql_contains": [
            "fact_leave_balance",
            "leave_type_name",
            "days_approved",
        ],
        "sql_contains_any_group": [
            ["fact_leave_transaction", "dim_leave_type"],
            ["fact_leave_balance"],
        ],
        "reject_sql": WORKFORCE_MART_ONLY_SQL,
    },
    {
        "id": "golden_attrition_rate",
        "question": ATTRITION_GOLDEN_Q,
        "expect_domain": ReportDomain.ATTRITION.value,
        "expect_template": "attrition.rate_by_department",
        "sql_contains": ["vw_turnover", "vw_headcount", "attrition_rate_pct"],
        "sql_excludes": [" AS attrition_rate,"],
    },
    {
        "id": "golden_attendance_summary",
        "question": ATTENDANCE_GOLDEN_Q,
        "expect_domain": ReportDomain.ATTENDANCE.value,
        "expect_template": "attendance.monthly_summary",
        "sql_contains": ["vw_attendance_summary", "TO_CHAR(CURRENT_DATE, 'YYYY-MM')"],
    },
    {
        "id": "golden_workforce_roster",
        "question": WORKFORCE_GOLDEN_Q,
        "expect_domain": ReportDomain.WORKFORCE.value,
        "expect_template": "workforce.roster",
        "sql_contains": [
            "mart_employee_current",
            "emp_fullname",
            "designation_department",
        ],
    },
    {
        "id": "golden_leave_not_workforce_template",
        "question": LEAVE_GOLDEN_Q,
        "expect_workforce_template_absent": True,
    },
    {
        "id": "golden_payroll_summary",
        "question": PAYROLL_GOLDEN_Q,
        "expect_domain": ReportDomain.PAYROLL.value,
        "expect_template": "payroll.summary_detail",
        "sql_contains": [
            "payroll_group_name",
            "payroll_frequency",
            "currency_code",
            "basic_salary",
        ],
        "sql_contains_any_group": [
            ["vw_payroll_summary", "dim_payroll_group"],
            ["mart_employee_current", "dim_payroll_group"],
        ],
    },
]

BROKER_CASES: list[dict[str, Any]] = [
    {
        "id": "broker_workforce_new",
        "question": "Generate a workforce report with employee name, company, branch",
        "last_sql": None,
        "expect_tables": ["mart_employee_current"],
        "expect_retrieval": "sufficient",
    },
    {
        "id": "broker_leave_detail",
        "question": LEAVE_GOLDEN_Q,
        "last_sql": None,
        "expect_any_tables": [
            "fact_leave_transaction",
            "fact_leave_balance",
            "vw_leave_summary",
        ],
        "expect_retrieval": "sufficient",
    },
    {
        "id": "broker_attrition",
        "question": ATTRITION_GOLDEN_Q,
        "last_sql": None,
        "expect_tables": ["vw_turnover", "vw_headcount"],
        "expect_retrieval": None,
    },
    {
        "id": "broker_attendance",
        "question": ATTENDANCE_GOLDEN_Q,
        "last_sql": None,
        "expect_tables": ["vw_attendance_summary"],
        "expect_retrieval": None,
    },
    {
        "id": "broker_payroll_topic",
        "question": "Show top 10 employees by basic salary from payroll",
        "last_sql": None,
        "expect_any_tables": [
            "fact_payroll_detail",
            "fact_payroll",
            "vw_payroll_summary",
        ],
        "expect_retrieval": None,
    },
]


def _golden_grounding(case_id: str) -> Optional[SchemaGrounding]:
    if case_id == "golden_leave_detail":
        return SchemaGrounding(
            columns_by_table={
                "hr.fact_leave_balance": [
                    "source_emp_id",
                    "leave_type_name",
                    "period_label",
                    "days_approved",
                ],
                "hr.dim_employee": [
                    "employee_id",
                    "employee_no",
                    "full_name",
                    "branch_name",
                    "is_current",
                ],
                "hr.mart_employee_current": [
                    "employee_id",
                    "emp_no",
                    "emp_fullname",
                    "location_name",
                ],
            },
            source="eval",
        )
    if case_id == "golden_attendance_summary":
        return SchemaGrounding(
            columns_by_table={
                "hr.vw_attendance_summary": [
                    "period_label",
                    "present_days",
                    "late_events",
                ],
            },
            source="eval",
        )
    if case_id == "golden_attrition_rate":
        return SchemaGrounding(
            columns_by_table={
                "hr.vw_turnover": ["department", "separations"],
                "hr.vw_headcount": ["department", "headcount"],
                "hr.mart_employee_current": ["designation_department"],
            },
            source="eval",
        )
    if case_id == "golden_workforce_roster":
        return SchemaGrounding(
            columns_by_table={
                "hr.mart_employee_current": [
                    "emp_fullname",
                    "emp_no",
                    "legal_entity",
                    "location_name",
                    "designation_department",
                    "emp_position",
                    "designation_id",
                    "superior_emp_no",
                ],
            },
            source="eval",
        )
    if case_id == "golden_payroll_summary":
        return SchemaGrounding(
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
            source="eval",
        )
    return None


def _check_fragments(sql: str, contains: list[str], excludes: list[str]) -> Optional[str]:
    for frag in contains:
        if frag not in sql:
            return f"missing SQL fragment: {frag!r}"
    for frag in excludes:
        if frag in sql:
            return f"forbidden SQL fragment present: {frag!r}"
    return None


def _check_any_group(sql: str, groups: list[list[str]]) -> Optional[str]:
    for group in groups:
        if all(frag in sql for frag in group):
            return None
    return f"SQL missing one of required table groups: {groups!r}"


def eval_golden_reports() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in GOLDEN_REPORT_CASES:
        q = case["question"]
        errors: list[str] = []

        if case.get("expect_workforce_template_absent"):
            wf = try_build_workforce_report_sql(q)
            if wf:
                errors.append("workforce template matched leave question")
            results.append(
                {
                    "id": case["id"],
                    "ok": not errors,
                    "kind": "golden_sql",
                    "errors": errors,
                }
            )
            continue

        spec = compile_report_spec(q, chat_intent=ChatIntent.NEW_QUERY)
        exp_domain = case.get("expect_domain")
        if exp_domain and spec.domain.value != exp_domain:
            errors.append(f"domain {spec.domain.value!r} != {exp_domain!r}")
        exp_tpl = case.get("expect_template")
        if exp_tpl and spec.template_id != exp_tpl:
            errors.append(f"template_id {spec.template_id!r} != {exp_tpl!r}")

        g = _golden_grounding(case["id"])
        routed = try_build_sql_from_report_spec(q, spec, grounding=g)
        if not routed and case["id"] == "golden_leave_detail":
            sql = try_build_leave_detail_report_sql(q, grounding=g)
            source = "leave_balance_template" if sql else None
            routed = (sql, source) if sql else None
        if not routed:
            errors.append("catalog SQL router returned None")
            sql = None
            source = None
        else:
            sql, source = routed
            frag_err = _check_fragments(
                sql,
                case.get("sql_contains") or [],
                case.get("sql_excludes") or [],
            )
            if frag_err:
                errors.append(frag_err)
            any_groups = case.get("sql_contains_any_group") or []
            if any_groups:
                group_err = _check_any_group(sql, any_groups)
                if group_err:
                    errors.append(group_err)
            if case["id"] != "golden_attendance_summary":
                spec_err = validate_sql_against_report_spec(q, sql, spec)
                if spec_err:
                    errors.append(f"spec validate: {spec_err}")

        reject_sql = case.get("reject_sql")
        if reject_sql and sql:
            bad_err = validate_sql_against_report_spec(q, reject_sql, spec)
            if not bad_err:
                errors.append("reject_sql should fail spec validation but passed")

        results.append(
            {
                "id": case["id"],
                "ok": not errors,
                "kind": "golden_sql",
                "domain": spec.domain.value,
                "template_id": spec.template_id,
                "sql_source": source,
                "errors": errors,
            }
        )
    return results


def eval_broker_retrieval() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in BROKER_CASES:
        q = case["question"]
        last_sql = case.get("last_sql")
        intent = classify_chat_intent(
            q,
            last_sql=last_sql,
            has_prior_post_process=False,
        )
        semantics = resolve_semantics(q)
        grounding = build_schema_grounding(
            question=q,
            mode=BrokerMode.CHAT,
            last_sql=last_sql,
            chat_intent=intent,
        )
        spec = compile_report_spec(q, chat_intent=intent or ChatIntent.NEW_QUERY)
        if spec.required_tables:
            grounding = ensure_grounding_includes_tables(
                grounding,
                spec.required_tables,
            )
        shorts = grounding.table_short_names
        expect = case.get("expect_tables") or []
        expect_any = case.get("expect_any_tables") or []
        if expect:
            tables_ok = all(any(e.lower() in t.lower() for t in shorts) for e in expect)
        elif expect_any:
            tables_ok = any(
                any(e.lower() in t.lower() for t in shorts) for e in expect_any
            )
        else:
            tables_ok = bool(shorts)

        links = build_schema_links(q, semantics, grounding)
        retrieval = validate_retrieval(
            question=q,
            grounding=grounding,
            semantics=semantics,
            schema_links=links,
            chat_intent=intent or ChatIntent.NEW_QUERY,
        )
        expect_retrieval = case.get("expect_retrieval")
        retrieval_ok = True
        if expect_retrieval:
            retrieval_ok = retrieval.status.value == expect_retrieval

        ok = tables_ok and retrieval_ok
        results.append(
            {
                "id": case["id"],
                "ok": ok,
                "kind": "broker",
                "intent": intent.value,
                "tables": shorts,
                "source": grounding.source,
                "topics": semantics.topics_matched,
                "retrieval_status": retrieval.status.value,
                "retrieval_missing": retrieval.missing_tables,
                "tables_ok": tables_ok,
                "retrieval_ok": retrieval_ok,
            }
        )
    return results


def main() -> None:
    golden = eval_golden_reports()
    broker = eval_broker_retrieval()
    results = golden + broker
    print(json.dumps(results, indent=2))

    golden_failed = [r["id"] for r in golden if not r["ok"]]
    broker_failed = [r["id"] for r in broker if not r["ok"]]

    if golden_failed:
        raise SystemExit(
            f"Golden SQL failed ({len(golden_failed)}): {', '.join(golden_failed)}"
        )
    if broker_failed:
        raise SystemExit(
            f"Broker retrieval failed ({len(broker_failed)}): {', '.join(broker_failed)} "
            "(needs warehouse/DataHub; CI uses mocked grounding in test_datamart_eval_ci.py)"
        )
    print(
        f"All eval cases passed "
        f"({len(GOLDEN_REPORT_CASES)} golden SQL + {len(BROKER_CASES)} broker)."
    )


if __name__ == "__main__":
    main()
