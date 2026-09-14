"""
S3 template modification: schema link (template mode) → LLM → unified verify.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from .. import config as dm_config
from ..orchestration.intent_router import ChatIntent
from ..llm.llm_client import LlmRole, call_llm
from ..llm.llm_response import (
    extract_narrative,
    extract_post_process_config,
    extract_sql,
    merge_post_process_configs,
)
from ..models import DatamartResponse
from ..workspace.observability import log_grounding, log_llm_response, log_pipeline_start
from ..validation.pipeline_validation import PipelineValidationState, finish_validated_response
from ..pipeline_trace import PipelineTracer
from ..pipeline_retry import RepairBudget
from ..llm.prompt_budget import build_user_prompt_within_budget, clip_text, is_context_length_error
from ..schema_broker import BrokerMode, build_schema_grounding
from ..prompts.template_prompts import TEMPLATE_USER_PROMPT_TEMPLATE, format_template_system_prompt
from ..orchestration.template_sql_guard import preserve_order_by_from_template
from ..config import (
    BROKER_MAX_PROMPT_CHARS,
    CHAT_HISTORY_MAX_CHARS,
    TEMPLATE_POST_PROCESS_JSON_MAX_CHARS,
    TEMPLATE_SQL_MAX_CHARS,
)
from ..sql.sql_retry import retry_on_error
from ..pipeline_trace import PipelineStepStatus, PipelineTracer
from .verify_sql import VerifyInput, verify_sql

logger = logging.getLogger("ai_services.datamart.template_runner")


def run_template_modification_pipeline(
    question: str,
    history_text: str,
    template_sql: str,
    template_narrative: str,
    template_post_process_config: Optional[list[dict]],
) -> DatamartResponse:
    log_pipeline_start(pipeline="template", question=question)
    trace = PipelineTracer.begin(
        repair_attempts_max=dm_config.DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN
    )
    repair_budget = RepairBudget(max_attempts=dm_config.DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN)

    grounding = build_schema_grounding(
        question=question,
        mode=BrokerMode.TEMPLATE,
        template_sql=template_sql,
    )
    if not grounding.columns_by_table:
        return DatamartResponse(
            question=question,
            narrative=(
                "I could not retrieve the database schema. "
                "Please check the warehouse connection."
            ),
            error="Schema unavailable",
        )

    pval = PipelineValidationState(question=question)
    if dm_config.DATAMART_VALIDATION_ENABLED:
        from ..validation.validation_runner import run_retrieval_validation

        retrieval_val, schema_links = run_retrieval_validation(
            question=question,
            grounding=grounding,
            chat_intent=ChatIntent.REFINE_SQL,
        )
        pval = PipelineValidationState(
            question=question,
            retrieval=retrieval_val,
            schema_links=schema_links,
        )
        if (
            dm_config.DATAMART_VALIDATION_ENFORCE_RETRIEVAL
            and retrieval_val.status.value == "insufficient"
        ):
            return finish_validated_response(
                pval,
                DatamartResponse(
                    question=question,
                    narrative=retrieval_val.message
                    or "Insufficient schema context for this template change.",
                    error="Retrieval insufficient",
                ),
                grounding=grounding,
                binding_passed=False,
            )

    schema_context = grounding.to_prompt_text()
    log_grounding(
        pipeline="template",
        source=grounding.source,
        tables=grounding.table_short_names,
    )

    if template_post_process_config:
        pp_json = clip_text(
            json.dumps(template_post_process_config, indent=2),
            TEMPLATE_POST_PROCESS_JSON_MAX_CHARS,
            "Post-processing JSON",
        )
        template_post_process_desc = f"Current post-processing:\n{pp_json}"
    else:
        template_post_process_desc = "No post-processing currently applied"

    sql_for_prompt = clip_text(template_sql, TEMPLATE_SQL_MAX_CHARS, "Template SQL")
    system_prompt = format_template_system_prompt()

    def _build_template_user(sc: str, ht: str) -> str:
        return TEMPLATE_USER_PROMPT_TEMPLATE.format(
            schema_context=sc,
            template_sql=sql_for_prompt,
            template_narrative=template_narrative or "(no description)",
            template_post_process_desc=template_post_process_desc,
            history_text=ht,
            question=question,
        )

    user_prompt, _est = build_user_prompt_within_budget(
        system_prompt,
        question,
        history_text,
        schema_context,
        schema_cap=BROKER_MAX_PROMPT_CHARS,
        history_cap=CHAT_HISTORY_MAX_CHARS,
        build_user=_build_template_user,
    )

    try:
        llm_output = call_llm(system_prompt, user_prompt, role=LlmRole.TEMPLATE)
    except Exception as exc:  # noqa: BLE001
        logger.error("Template modification LLM call failed: %s", exc)
        if is_context_length_error(exc):
            return finish_validated_response(
                pval,
                DatamartResponse(
                    question=question,
                    narrative=(
                        "The template plus schema context is too large for the AI model. "
                        "Try a shorter modification request."
                    ),
                    error="Context length exceeded",
                ),
                sql=template_sql,
                grounding=grounding,
                binding_passed=False,
            )
        from ..llm.llm_settings import format_llm_error

        narrative, err_code = format_llm_error(exc)
        return finish_validated_response(
            pval,
            DatamartResponse(question=question, narrative=narrative, error=err_code),
            sql=template_sql,
            grounding=grounding,
            binding_passed=False,
        )

    log_llm_response(
        pipeline="template",
        chars=len(llm_output),
        parsed_sql=bool(extract_sql(llm_output)),
    )

    narrative = extract_narrative(llm_output)
    modified_sql = extract_sql(llm_output)
    new_post_process_config = extract_post_process_config(llm_output)

    if modified_sql is None:
        modified_sql = template_sql
        logger.info("LLM indicated modification cannot be applied; returning original SQL")

    merged_sql, order_merged = preserve_order_by_from_template(template_sql, modified_sql)
    if order_merged:
        modified_sql = merged_sql
        note = (
            "\n\n[System: Original ORDER BY columns were preserved and new sort "
            "keys were appended so the same rows remain in the result set.]"
        )
        narrative = (narrative + note).strip() if narrative else note.strip()

    trace.start("generate_sql")
    trace.complete("generate_sql", PipelineStepStatus.COMPLETED, "Template LLM edit")

    result = verify_sql(
        VerifyInput(
            question=question,
            sql=modified_sql,
            narrative=narrative,
            post_process_config=new_post_process_config,
            grounding=grounding,
            system_prompt=system_prompt,
            catalog_governed=False,
            use_verified_metric=False,
            sql_source="template_llm",
            report_spec=None,
            chat_intent=ChatIntent.REFINE_SQL,
            anchor_sql=template_sql,
            broker_last_sql=template_sql,
            is_modify=True,
        ),
        trace=trace,
        repair_budget=repair_budget,
        retry_fn=retry_on_error,
    )

    if result.blocked or not result.passed:
        return finish_validated_response(
            pval,
            DatamartResponse(
                question=question,
                narrative=(
                    f"{result.narrative}\n\n⚠️ The suggested SQL could not be verified: "
                    f"{result.detail}"
                ),
                sql=template_sql,
                post_process_config=template_post_process_config,
                error=result.detail,
            ),
            sql=result.sql,
            grounding=result.grounding,
            binding_passed=False,
        )

    merged_pp = merge_post_process_configs(
        template_post_process_config, result.post_process_config
    )

    return finish_validated_response(
        pval,
        DatamartResponse(
            question=question,
            narrative=result.narrative,
            sql=result.sql,
            post_process_config=merged_pp,
            error=None,
        ),
        sql=result.sql,
        grounding=result.grounding,
        binding_passed=True,
    )
