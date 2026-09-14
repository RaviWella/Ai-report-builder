"""
S2 SQL resolver: Tier A → B → C (plan-then-SQL) with link-table enforcement.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from .. import config as dm_config
from ..orchestration.clarification_flow import looks_like_clarification_narrative
from ..orchestration.intent_router import ChatIntent
from ..llm.llm_client import LlmRole, call_llm
from ..llm.llm_response import extract_narrative, extract_post_process_config, is_stub_sql
from ..workspace.observability import log_llm_response, log_repair
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from ..validation.pipeline_validation import PipelineValidationState
from ..domain_sql.report_spec import ReportSpec
from ..schema_broker import SchemaGrounding
from ..sql.sql_generation import finish_generate_sql_trace, parse_sql_from_llm_output, recover_sql_after_llm
from .artifacts import SqlArtifact
from .query_plan import build_query_plan, clarification_from_plan
from .sql_table_guard import assert_sql_tables_in_link
from .tier_probe import try_resolve_tier_ab

logger = logging.getLogger("ai_services.datamart.sql_resolver")

CATALOG_TEMPLATE_SOURCES = frozenset(
    {
        "employee_list_template",
        "employee_shift_template",
        "recruitment_pipeline_template",
        "employee_bank_detail_template",
        "attendance_summary_template",
        "leave_detail_template",
        "leave_summary_view_template",
        "leave_balance_template",
        "payroll_summary_view_template",
        "payroll_mart_group_template",
        "payroll_fact_template",
        "payroll_processed_summary_template",
        "attrition_rate_template",
        "headcount_breakdown_template",
        "top_paid_template",
        "workforce_template",
        "verified_metric",
    }
)


def _tier_label(source: Optional[str]) -> str:
    if not source:
        return "C"
    if source == "verified_metric" or (source in CATALOG_TEMPLATE_SOURCES):
        return "A"
    if source.startswith("verified:"):
        return "B"
    return "C"


def _is_catalog_source(source: Optional[str]) -> bool:
    return bool(
        source
        and (
            source in CATALOG_TEMPLATE_SOURCES
            or source.startswith("verified:")
            or source == "verified_metric"
        )
    )


def resolve_sql_artifact(
    *,
    question: str,
    history_text: str,
    grounding: SchemaGrounding,
    system_prompt: str,
    user_prompt: str,
    trace: PipelineTracer,
    chat_intent: ChatIntent,
    report_spec: Optional[ReportSpec],
    is_modify: bool,
    is_add_scenario: bool,
    targets: list[str],
    pval: PipelineValidationState,
    domain: str | None = None,
) -> SqlArtifact:
    llm_output = ""
    query_plan = None
    post_process_config: Optional[list] = None

    trace.start("generate_sql")

    ab = try_resolve_tier_ab(
        question=question,
        grounding=grounding,
        chat_intent=chat_intent,
        report_spec=report_spec,
        is_modify=is_modify,
        is_add_scenario=is_add_scenario,
        targets=targets,
        pval=pval,
        domain=domain,
    )
    if ab:
        trace.complete(
            "generate_sql",
            PipelineStepStatus.COMPLETED,
            f"Tier {ab.tier} ({ab.source})",
        )
        sql = ab.sql
        narrative = ab.narrative
        sql_source = ab.source
        use_verified_metric = ab.use_verified_metric
    else:
        sql = None
        narrative = ""
        sql_source = None
        use_verified_metric = False

        query_plan = build_query_plan(question, grounding=grounding, domain=domain)
        plan_clarify = clarification_from_plan(query_plan)
        if plan_clarify:
            trace.complete(
                "generate_sql",
                PipelineStepStatus.BLOCKED,
                "Query plan needs clarification",
            )
            return SqlArtifact(
                sql=None,
                narrative=plan_clarify,
                post_process_config=None,
                source=None,
                tier="C",
                query_plan=query_plan,
                grounding=grounding,
                needs_clarification=True,
                clarification_message=plan_clarify,
            )

        plan_addon = ""
        if query_plan:
            plan_addon = "\n\n" + query_plan.to_prompt_block() + "\n"
            trace.note_repair("Query plan attached for Tier C", success=True)

        tier_c_user = user_prompt + plan_addon
        t0 = time.perf_counter()
        llm_output = call_llm(system_prompt, tier_c_user, role=LlmRole.CHAT)
        logger.info("Tier C LLM completed in %dms", int((time.perf_counter() - t0) * 1000))

        log_llm_response(
            pipeline="chat",
            chars=len(llm_output),
            parsed_sql=bool(parse_sql_from_llm_output(llm_output)),
        )
        narrative = extract_narrative(llm_output)
        sql = parse_sql_from_llm_output(llm_output)
        post_process_config = extract_post_process_config(llm_output)
        sql_source = "llm" if sql else None

        recovered = recover_sql_after_llm(
            question=question,
            history_text=history_text,
            narrative=narrative,
            llm_output=llm_output,
            llm_sql=sql,
            post_process_config=post_process_config,
            grounding=grounding,
        )
        sql = recovered.sql
        narrative = recovered.narrative
        post_process_config = recovered.post_process_config
        sql_source = recovered.source or sql_source
        if recovered.source and recovered.source.startswith("repair"):
            log_repair(kind="recover", success=True)

        if dm_config.DATAMART_BLOCK_STUB_SQL and is_stub_sql(sql):
            logger.warning("Blocked stub SQL from Tier C / repair")
            sql = None
            sql_source = None

        if sql is None and looks_like_clarification_narrative(narrative):
            trace.complete(
                "generate_sql",
                PipelineStepStatus.BLOCKED,
                "Clarification required",
            )
            return SqlArtifact(
                sql=None,
                narrative=narrative,
                post_process_config=post_process_config,
                source=None,
                tier="C",
                llm_output=llm_output,
                query_plan=query_plan,
                grounding=grounding,
                needs_clarification=True,
                clarification_message=narrative,
            )

        finish_generate_sql_trace(trace, sql=sql, source=sql_source or "llm_plan")

    if sql:
        link_err = assert_sql_tables_in_link(sql, grounding)
        if link_err:
            logger.warning("SQL failed link-table guard: %s", link_err)
            if _is_catalog_source(sql_source):
                trace.complete(
                    "generate_sql",
                    PipelineStepStatus.WARNING,
                    f"Governed SQL link guard: {link_err[:120]}",
                )
            else:
                sql = None
                sql_source = None
                trace.complete(
                    "generate_sql",
                    PipelineStepStatus.FAILED,
                    link_err[:220],
                )

    tier = _tier_label(sql_source)
    return SqlArtifact(
        sql=sql,
        narrative=narrative,
        post_process_config=post_process_config,
        source=sql_source,
        tier=tier,
        llm_output=llm_output,
        query_plan=query_plan,
        grounding=grounding,
        catalog_governed=_is_catalog_source(sql_source),
        use_verified_metric=use_verified_metric,
    )
