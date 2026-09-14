"""
Resolve executable SQL after the LLM turn (templates, repairs, parsing).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ..llm.llm_response import extract_sql, normalize_executable_sql
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from .sql_repairs import attempt_missing_sql_repair, attempt_per_group_sql_repair
from ..schema_broker import SchemaGrounding
from ..domain_sql.catalog_report_sql import (
    try_build_attendance_summary_sql,
    try_build_attrition_rate_report_sql,
)
from ..domain_sql.leave_report_sql import try_build_leave_detail_report_sql
from ..domain_sql.payroll_report_sql import try_build_payroll_detail_report_sql
from ..domain_sql.employee_bank_detail_sql import try_build_employee_bank_detail_sql
from ..domain_sql.recruitment_pipeline_sql import try_build_recruitment_pipeline_sql
from ..domain_sql.workforce_sql_template import (
    try_build_top_paid_report_sql,
    try_build_workforce_report_sql,
)

logger = logging.getLogger("ai_services.datamart.sql_generation")


@dataclass
class SqlGenerationOutcome:
    sql: Optional[str]
    narrative: str
    post_process_config: Optional[list[dict]]
    source: Optional[str]  # llm | attrition_rate_template | workforce_template | ...


def try_workforce_template_sql(question: str) -> Optional[str]:
    return try_build_workforce_report_sql(question)


def try_top_paid_template_sql(question: str) -> Optional[str]:
    return try_build_top_paid_report_sql(question)


def try_attrition_rate_template_sql(question: str) -> Optional[str]:
    return try_build_attrition_rate_report_sql(question)


def try_attendance_summary_template_sql(question: str) -> Optional[str]:
    return try_build_attendance_summary_sql(question)


def try_leave_detail_template_sql(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[str]:
    return try_build_leave_detail_report_sql(question, grounding=grounding)


def try_payroll_detail_template_sql(
    question: str,
    *,
    grounding: Optional[SchemaGrounding] = None,
) -> Optional[str]:
    return try_build_payroll_detail_report_sql(question, grounding=grounding)


def finish_generate_sql_trace(
    trace: PipelineTracer,
    *,
    sql: Optional[str],
    source: Optional[str],
) -> None:
    """Record final generate_sql status after LLM + all recovery paths."""
    if sql and source == "llm":
        trace.complete("generate_sql", PipelineStepStatus.COMPLETED, "LLM draft SQL")
    elif sql and source == "leave_detail_template":
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "Leave detail report SQL (catalog template)",
        )
    elif sql and source == "attendance_summary_template":
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "Attendance summary SQL (catalog template)",
        )
    elif sql and source == "attrition_rate_template":
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "Attrition rate by dimension (catalog template)",
        )
    elif sql and source == "top_paid_template":
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "Top paid employees SQL (catalog template)",
        )
    elif sql and source == "workforce_template":
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "Workforce report SQL (catalog template)",
        )
    elif sql and source and source.startswith("payroll_"):
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "Payroll summary SQL (catalog template)",
        )
    elif sql and source in ("repair_per_group", "repair_missing"):
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            "SQL recovered (repair pass)",
        )
    elif sql and source == "verified_metric":
        pass  # caller already completed trace
    elif sql:
        trace.complete("generate_sql", PipelineStepStatus.COMPLETED, "SQL ready")
    else:
        trace.complete(
            "generate_sql",
            PipelineStepStatus.WARNING,
            "No SQL after LLM and recovery attempts",
        )


def recover_sql_after_llm(
    *,
    question: str,
    history_text: str,
    narrative: str,
    llm_output: str,
    llm_sql: Optional[str],
    post_process_config: Optional[list[dict]],
    grounding: SchemaGrounding,
) -> SqlGenerationOutcome:
    """
  If the LLM omitted SQL, try workforce template then repair passes.
  """
    sql = llm_sql
    source: Optional[str] = "llm" if sql else None
    pp = post_process_config
    narr = narrative

    if sql and re.search(r"\bmart_employee_current\b", sql, re.I):
        leave_fix = try_build_leave_detail_report_sql(question, grounding=grounding)
        if leave_fix:
            logger.info("Replacing workforce mart SQL with leave detail catalog template")
            return SqlGenerationOutcome(
                sql=leave_fix,
                narrative=narr or (
                    "Leave requests joined to employees and leave types "
                    "(approved filter applied when requested)."
                ),
                post_process_config=pp,
                source="leave_detail_template",
            )

    if sql and re.search(r"\battrition_rate\b|\bturnover_rate\b", sql, re.I):
        replacement = try_build_attrition_rate_report_sql(question)
        if replacement:
            logger.info("Replacing LLM SQL with attrition-rate catalog template")
            return SqlGenerationOutcome(
                sql=replacement,
                narrative=narr or (
                    "Attrition rate by department from vw_turnover and vw_headcount."
                ),
                post_process_config=pp,
                source="attrition_rate_template",
            )

    if sql is None:
        recruitment = try_build_recruitment_pipeline_sql(
            question, grounding=grounding
        )
        if recruitment:
            logger.info(
                "Using recruitment pipeline SQL template (LLM returned no SQL)"
            )
            return SqlGenerationOutcome(
                sql=recruitment,
                narrative=narr or (
                    "Recruitment pipeline candidates with source, dates, and branch."
                ),
                post_process_config=pp,
                source="recruitment_pipeline_template",
            )

        attendance = try_build_attendance_summary_sql(question)
        if attendance:
            logger.info("Using attendance summary SQL template (LLM returned no SQL)")
            sql = attendance
            source = "attendance_summary_template"
            narr = narr or (
                "Monthly attendance summary from vw_attendance_summary "
                "(present days, late events, overtime hours)."
            )
        else:
            leave_detail = try_build_leave_detail_report_sql(
                question, grounding=grounding
            )
            if leave_detail:
                logger.info("Using leave detail SQL template (LLM returned no SQL)")
                sql = leave_detail
                source = "leave_detail_template"
                narr = narr or (
                    "Employee leave transactions with type, dates, days, and status."
                )
            else:
                payroll_detail = try_build_payroll_detail_report_sql(
                    question, grounding=grounding
                )
                if payroll_detail:
                    logger.info("Using payroll summary SQL template (LLM returned no SQL)")
                    sql = payroll_detail
                    source = "payroll_summary_view_template"
                    narr = narr or (
                        "Payroll summary from vw_payroll_summary with payroll group "
                        "frequency and currency when available."
                    )
                else:
                    attrition = try_build_attrition_rate_report_sql(question)
                    if attrition:
                        logger.info(
                            "Using attrition-rate report SQL template (LLM returned no SQL)"
                        )
                        sql = attrition
                        source = "attrition_rate_template"
                        narr = narr or (
                            "Attrition rate by department from separations (vw_turnover) "
                            "over active headcount (vw_headcount)."
                        )
                    else:
                        top_paid = try_build_top_paid_report_sql(question)
                        if top_paid:
                            logger.info(
                                "Using top-paid report SQL template (LLM returned no SQL)"
                            )
                            sql = top_paid
                            source = "top_paid_template"
                            narr = narr or (
                                "Ranking employees by basic salary from the workforce mart."
                            )
                        else:
                            bank_detail = try_build_employee_bank_detail_sql(
                                question, grounding=grounding
                            )
                            if bank_detail:
                                logger.info(
                                    "Using employee+bank detail SQL template "
                                    "(LLM returned no SQL)"
                                )
                                sql = bank_detail
                                source = "employee_bank_detail_template"
                                narr = narr or (
                                    "Employee number, name, employment category, "
                                    "and bank details from the workforce mart "
                                    "and salary bank instruction tables."
                                )
                            else:
                                fallback = try_build_workforce_report_sql(question)
                                if fallback:
                                    logger.info(
                                        "Using workforce report SQL template "
                                        "(LLM returned no SQL)"
                                    )
                                    sql = fallback
                                    source = "workforce_template"
                                    narr = narr or (
                                        "Listing current employees from the workforce mart "
                                        "with name, ID, company, branch, department, "
                                        "and reporting manager."
                                    )

    if sql is None:
        n2, s2, p2 = attempt_per_group_sql_repair(
            question, history_text, narr, llm_output
        )
        if s2:
            return SqlGenerationOutcome(
                sql=normalize_executable_sql(s2),
                narrative=n2 or narr,
                post_process_config=p2 or pp,
                source="repair_per_group",
            )
        n2, s2, p2 = attempt_missing_sql_repair(
            question, grounding, narr, llm_output
        )
        if s2:
            return SqlGenerationOutcome(
                sql=normalize_executable_sql(s2),
                narrative=n2 or narr,
                post_process_config=p2 or pp,
                source="repair_missing",
            )
        attendance = try_build_attendance_summary_sql(question)
        if attendance:
            logger.info("Using attendance summary template after repair failed")
            return SqlGenerationOutcome(
                sql=attendance,
                narrative=narr or "Monthly attendance summary from vw_attendance_summary.",
                post_process_config=pp,
                source="attendance_summary_template",
            )
        leave_detail = try_build_leave_detail_report_sql(
            question, grounding=grounding
        )
        if leave_detail:
            logger.info("Using leave detail template after repair failed")
            return SqlGenerationOutcome(
                sql=leave_detail,
                narrative=narr or "Employee leave transactions with type, dates, and status.",
                post_process_config=pp,
                source="leave_detail_template",
            )
        payroll_detail = try_build_payroll_detail_report_sql(
            question, grounding=grounding
        )
        if payroll_detail:
            logger.info("Using payroll summary template after repair failed")
            return SqlGenerationOutcome(
                sql=payroll_detail,
                narrative=narr or (
                    "Payroll summary from vw_payroll_summary with payroll group details."
                ),
                post_process_config=pp,
                source="payroll_summary_view_template",
            )
        attrition = try_build_attrition_rate_report_sql(question)
        if attrition:
            logger.info("Using attrition-rate template after repair failed")
            return SqlGenerationOutcome(
                sql=attrition,
                narrative=narr or (
                    "Attrition rate by department from vw_turnover and vw_headcount."
                ),
                post_process_config=pp,
                source="attrition_rate_template",
            )
        top_paid = try_build_top_paid_report_sql(question)
        if top_paid:
            logger.info("Using top-paid report SQL template after repair failed")
            return SqlGenerationOutcome(
                sql=top_paid,
                narrative=narr or "Ranking employees by basic salary from the workforce mart.",
                post_process_config=pp,
                source="top_paid_template",
            )
        fallback = try_build_workforce_report_sql(question)
        if fallback:
            logger.info("Using workforce report SQL template after repair failed")
            return SqlGenerationOutcome(
                sql=fallback,
                narrative=narr or "Listing current employees from the workforce mart.",
                post_process_config=pp,
                source="workforce_template",
            )

    return SqlGenerationOutcome(
        sql=sql,
        narrative=narr,
        post_process_config=pp,
        source=source,
    )


def parse_sql_from_llm_output(llm_output: str) -> Optional[str]:
    """Parse executable SQL from a structured LLM reply."""
    return normalize_executable_sql(extract_sql(llm_output))
