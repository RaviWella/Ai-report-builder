"""
Pre-execute validation against ReportSpec (fast sqlglot + string rules).

Blocks wrong-domain SQL before warehouse execution.
"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp

from ..llm.llm_response import is_non_executable_sql
from ..domain_sql.metric_templates import is_scalar_aggregate_sql, question_wants_row_detail
from ..domain_sql.report_spec import (
    ReportDomain,
    ReportSpec,
    ReportType,
    field_sql_fragments,
    spec_required_tables,
)
from ..schema import list_warehouse_tables


def _tables_in_sql(sql: str) -> set[str]:
    try:
        tree = sqlglot.parse_one(sql, dialect="postgres")
    except Exception:  # noqa: BLE001
        return set()
    names: set[str] = set()
    for table in tree.find_all(exp.Table):
        if table.name:
            names.add(table.name.lower())
    return names


def _has_filter(sql_l: str, filter_key: str) -> bool:
    if filter_key == "approved_leave":
        return bool(
            re.search(r"leave_status_name\s+ilike\s+'%approved%'", sql_l, re.I)
            or re.search(r"leave_status.*approved", sql_l, re.I)
            or re.search(r"\bapproved\b", sql_l, re.I)
        )
    if filter_key == "current_month":
        return "to_char(current_date" in sql_l or "current_date" in sql_l
    return True


def _warehouse_table_names() -> set[str]:
    return {t.lower() for t in list_warehouse_tables()}


_LEAVE_EMPLOYEE_SOURCES = frozenset(
    {"dim_employee", "mart_employee_current", "snap_employee"}
)
_LEAVE_FACT_SOURCES = frozenset(
    {
        "fact_leave_balance",
        "fact_leave_transaction",
        "vw_leave_summary",
    }
)


_PAYROLL_EMPLOYEE_SOURCES = frozenset(
    {"dim_employee", "mart_employee_current", "snap_employee"}
)
_PAYROLL_FACT_SOURCES = frozenset(
    {
        "vw_payroll_summary",
        "mart_processed_payroll_summary",
        "fact_payroll",
        "fct_processed_salary",
    }
)


_ATTENDANCE_SUMMARY_SOURCES = frozenset(
    {"vw_attendance_summary", "mart_attendance_monthly_summary"}
)


def _attendance_table_requirements_met(
    tables: set[str],
    report_type: ReportType,
) -> tuple[bool, list[str]]:
    if report_type == ReportType.SUMMARY:
        if tables & _ATTENDANCE_SUMMARY_SOURCES:
            return True, []
        return False, ["vw_attendance_summary or mart_attendance_monthly_summary"]
    missing: list[str] = []
    if not (tables & {"fact_attendance", "fct_daily_attendance"}):
        missing.append("fact_attendance or fct_daily_attendance")
    return (not missing, missing)


_WORKFORCE_EMPLOYEE_SOURCES = frozenset(
    {"mart_employee_current", "dim_employee", "snap_employee"}
)


def _workforce_table_requirements_met(tables: set[str]) -> tuple[bool, list[str]]:
    if tables & _WORKFORCE_EMPLOYEE_SOURCES:
        return True, []
    return False, ["mart_employee_current or dim_employee"]


def _payroll_table_requirements_met(tables: set[str]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if not (tables & _PAYROLL_EMPLOYEE_SOURCES) and "vw_payroll_summary" not in tables:
        missing.append("employee source (mart_employee_current or dim_employee)")
    if not (tables & _PAYROLL_FACT_SOURCES):
        if not (tables & _PAYROLL_EMPLOYEE_SOURCES and "dim_payroll_group" in tables):
            missing.append(
                "payroll source (vw_payroll_summary, fact_payroll, or mart + dim_payroll_group)"
            )
    return (not missing, missing)


def _leave_table_requirements_met(tables: set[str]) -> tuple[bool, list[str]]:
    """Return (ok, missing human labels) for leave detail SQL table coverage."""
    missing: list[str] = []
    if not (tables & _LEAVE_EMPLOYEE_SOURCES):
        missing.append("employee source (dim_employee or mart_employee_current)")
    if not (tables & _LEAVE_FACT_SOURCES):
        missing.append("leave source (fact_leave_balance or fact_leave_transaction)")
    if "fact_leave_transaction" in tables and "dim_leave_type" not in tables:
        missing.append("dim_leave_type")
    return (not missing, missing)


def validate_retrieval_for_spec(
    spec: ReportSpec,
    table_short_names: list[str],
) -> Optional[str]:
    """Ensure grounding includes spec-required tables."""
    if not spec.required_tables:
        return None
    have = {t.lower() for t in table_short_names}
    required = spec_required_tables(spec)
    wh = _warehouse_table_names()
    # Do not require tables that are not deployed in this tenant warehouse.
    if wh:
        required = {t for t in required if t.lower() in wh or t.lower() in have}
    missing = sorted(required - have)
    if spec.domain == ReportDomain.LEAVE and missing:
        leave_alternatives = have & {
            "vw_leave_summary",
            "fact_leave_balance",
            "fact_leave_transaction",
        }
        if leave_alternatives and set(missing) <= {
            "fact_leave_transaction",
            "dim_leave_type",
            "vw_leave_summary",
            "fact_leave_balance",
        }:
            return None
    if spec.domain == ReportDomain.PAYROLL and missing:
        payroll_ok = have & {"vw_payroll_summary", "mart_processed_payroll_summary"}
        mart_pg = {"mart_employee_current", "dim_payroll_group"} <= have
        if payroll_ok or mart_pg:
            optional = {
                "fact_payroll",
                "fct_processed_salary",
                "dim_employee",
                "mart_employee_current",
                "dim_payroll_group",
                "vw_payroll_summary",
                "mart_processed_payroll_summary",
            }
            if set(missing) <= optional:
                return None
    if spec.domain == ReportDomain.WORKFORCE and missing:
        # Roster / supervisor lists use denormalized mart columns; dim_employee is optional.
        if "mart_employee_current" in have:
            optional = {
                "dim_employee",
                "snap_employee",
                "dim_org_unit",
                "dim_designation",
                "dim_company",
                "dim_branch",
            }
            if set(missing) <= optional:
                return None
    if spec.domain == ReportDomain.ATTENDANCE and missing:
        attendance_sources = _ATTENDANCE_SUMMARY_SOURCES | {
            "fact_attendance",
            "fct_daily_attendance",
        }
        employee_sources = _WORKFORCE_EMPLOYEE_SOURCES
        optional = attendance_sources | employee_sources | {
            "dim_org_unit",
            "dim_designation",
            "dim_company",
            "dim_branch",
        }
        if (have & attendance_sources) or (have & employee_sources):
            if set(missing) <= optional:
                return None
    if not missing:
        return None
    return (
        f"Grounded schema is missing tables required for {spec.domain.value} "
        f"({spec.report_type.value}): {', '.join(missing)}."
    )


def validate_sql_against_report_spec(
    question: str,
    sql: Optional[str],
    spec: ReportSpec,
) -> Optional[str]:
    """
    Return error message if SQL cannot satisfy the compiled report spec; else None.
    """
    if is_non_executable_sql(sql):
        return "No SQL was produced for this question."

    sql_l = (sql or "").lower()
    tables = _tables_in_sql(sql or "")

    # Wrong-domain: only workforce mart when leave/attendance detail expected
    for forbidden in spec.forbidden_table_only:
        fb = forbidden.lower()
        if fb in tables and len(tables) == 1:
            return (
                f"This question requires {spec.domain.value} data, but SQL only queries "
                f"{forbidden}. Use the tables: {', '.join(spec.required_tables)}."
            )
        if spec.domain == ReportDomain.LEAVE and fb in tables:
            if "fact_leave_balance" in tables or "fact_leave_transaction" in tables:
                pass
            elif "vw_leave_summary" not in tables:
                return (
                    "Leave report must join fact_leave_transaction (and dim_leave_type), "
                    "not only mart_employee_current."
                )

    if spec.required_tables and spec.report_type != ReportType.SCALAR:
        if spec.domain == ReportDomain.LEAVE:
            ok, missing_labels = _leave_table_requirements_met(tables)
            if not ok:
                return (
                    f"SQL must use {spec.domain.value} source table(s); missing: "
                    + ", ".join(missing_labels)
                )
        elif spec.domain == ReportDomain.PAYROLL:
            ok, missing_labels = _payroll_table_requirements_met(tables)
            if not ok:
                return (
                    f"SQL must use {spec.domain.value} source table(s); missing: "
                    + ", ".join(missing_labels)
                )
        elif spec.domain == ReportDomain.ATTENDANCE:
            ok, missing_labels = _attendance_table_requirements_met(
                tables, spec.report_type
            )
            if not ok:
                return (
                    f"SQL must use {spec.domain.value} source table(s); missing: "
                    + ", ".join(missing_labels)
                )
        elif spec.domain == ReportDomain.WORKFORCE:
            ok, missing_labels = _workforce_table_requirements_met(tables)
            if not ok:
                return (
                    f"SQL must use {spec.domain.value} source table(s); missing: "
                    + ", ".join(missing_labels)
                )
        else:
            required_tables = spec_required_tables(spec)
            missing_tables = sorted(required_tables - tables)
            if missing_tables:
                primary = next(iter(required_tables), spec.required_tables[0]).lower()
                if primary not in tables:
                    return (
                        f"SQL must use {spec.domain.value} source table(s); missing: "
                        + ", ".join(missing_tables)
                    )

    for fkey in spec.sql_filters:
        if not _has_filter(sql_l, fkey):
            if fkey == "approved_leave":
                return (
                    "Question asks for approved leave only, but SQL has no "
                    "leave_status_name filter for approved requests."
                )

    if spec.report_type == ReportType.DETAIL_LIST and spec.required_output_columns:
        missing_fields: list[str] = []
        for field_id in spec.required_output_columns:
            frags = field_sql_fragments(field_id)
            if not any(frag in sql_l for frag in frags):
                missing_fields.append(field_id.replace("_", " "))
        if missing_fields:
            return (
                "SQL is missing required output fields: "
                + ", ".join(missing_fields)
                + ". Add them to SELECT from the grounded tables."
            )

    if spec.report_type == ReportType.DETAIL_LIST and question_wants_row_detail(question):
        try:
            tree = sqlglot.parse_one(sql, dialect="postgres")
            if is_scalar_aggregate_sql(sql):
                return (
                    "Question asks for a multi-column report, but SQL returns only "
                    "a single aggregate."
                )
            select = tree.find(exp.Select)
            if select:
                n_exprs = sum(
                    1 for e in select.expressions if not isinstance(e, exp.Star)
                )
                if spec.required_output_columns and n_exprs < len(spec.required_output_columns):
                    return (
                        f"SQL projects {n_exprs} column(s) but the question needs "
                        f"about {len(spec.required_output_columns)} attributes."
                    )
        except Exception:  # noqa: BLE001
            pass

    return None
