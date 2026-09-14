"""Orchestrate retrieval + generation validation for chat/template pipelines."""
from __future__ import annotations

from typing import Optional

from .. import config as dm_config
from ..orchestration.intent_router import ChatIntent
from .retrieval_validator import validate_retrieval
from ..schema_broker import BrokerMode, SchemaGrounding, build_schema_grounding
from ..orchestration.schema_linker import build_schema_links
from ..semantic.semantic_layer import resolve_semantics
from ..sql.sql_faithfulness import check_sql_faithfulness
from .trust_scorer import build_datamart_validation, compute_trust_level
from ..models import DatamartResponse, GroundingPreviewResponse
from .validation_models import (
    DatamartValidation,
    GenerationValidation,
    RetrievalValidation,
    ValidationStatus,
)


def run_retrieval_validation(
    *,
    question: str,
    grounding: SchemaGrounding,
    chat_intent: ChatIntent,
) -> tuple[RetrievalValidation, list]:
    """Return retrieval validation and schema links."""
    semantics = resolve_semantics(question)
    links = build_schema_links(question, semantics, grounding)
    retrieval = validate_retrieval(
        question=question,
        grounding=grounding,
        semantics=semantics,
        schema_links=links,
        chat_intent=chat_intent,
    )
    return retrieval, links


def run_generation_validation(
    *,
    question: str,
    sql: Optional[str],
    grounding: SchemaGrounding,
    schema_links: list,
    binding_passed: bool,
    row_count: int = 0,
    grounding_expanded: bool = False,
    run_critic: bool = True,
) -> Optional[GenerationValidation]:
    if not sql or not dm_config.DATAMART_VALIDATION_FAITHFULNESS:
        return None
    gen = check_sql_faithfulness(
        question=question,
        sql=sql,
        grounding=grounding,
        schema_links=schema_links,
        binding_passed=binding_passed,
    )
    gen.grounding_expanded = grounding_expanded
    gen.truncated = row_count >= dm_config.MAX_RESULT_ROWS
    if run_critic and dm_config.DATAMART_VALIDATION_CRITIC:
        from ..sql.sql_generation_critic import run_sql_generation_critic

        ok, issues = run_sql_generation_critic(
            question=question,
            sql=sql,
            grounding=grounding,
            schema_summary=grounding.to_prompt_text(),
        )
        if not ok:
            for issue in issues:
                if issue and issue not in gen.warnings:
                    gen.warnings.append(issue)
    return gen


def attach_validation_to_response(
    response: DatamartResponse,
    retrieval: Optional[RetrievalValidation],
    *,
    generation: Optional[GenerationValidation] = None,
) -> DatamartResponse:
    validation = merge_validation(retrieval, generation, response.error)
    if validation is None:
        return response
    return response.model_copy(update={"validation": validation})


def validate_extra_result_block(
    *,
    question: str,
    sql: Optional[str],
    grounding: SchemaGrounding,
    schema_links: list,
    binding_passed: bool,
    row_count: int = 0,
    error: Optional[str] = None,
    retrieval: Optional[RetrievalValidation] = None,
) -> Optional[dict]:
    """Compact validation dict for one extra result block (scoped to that scenario)."""
    if not dm_config.DATAMART_VALIDATION_ENABLED:
        return None
    ret = retrieval or RetrievalValidation(
        status=ValidationStatus.SUFFICIENT,
        tables_selected=[],
    )
    if not sql:
        overall = compute_trust_level(retrieval=ret, generation=None, error=error or "No SQL")
        return {
            "overall": overall.value,
            "retrieval": ret.model_dump(mode="json"),
            "generation": {"binding": "failed", "warnings": [error or "No SQL"]},
        }
    gen = run_generation_validation(
        question=question,
        sql=sql,
        grounding=grounding,
        schema_links=schema_links,
        binding_passed=binding_passed,
        row_count=row_count,
    )
    overall = compute_trust_level(
        retrieval=ret,
        generation=gen,
        error=error,
    )
    payload: dict = {
        "overall": overall.value,
        "retrieval": ret.model_dump(mode="json"),
    }
    if gen:
        payload["generation"] = gen.model_dump(mode="json")
    return payload


def build_grounding_preview(
    *,
    question: str,
    chat_intent: ChatIntent,
    last_sql: Optional[str] = None,
    confirmed_tables: Optional[list[str]] = None,
) -> GroundingPreviewResponse:
    grounding = build_schema_grounding(
        question=question,
        mode=BrokerMode.CHAT,
        last_sql=last_sql,
        chat_intent=chat_intent,
        confirmed_table_names=confirmed_tables,
    )
    if not grounding.columns_by_table:
        empty = RetrievalValidation(
            status=ValidationStatus.INSUFFICIENT,
            message="Schema unavailable — check warehouse connection.",
        )
        return GroundingPreviewResponse(
            question=question,
            retrieval=empty,
            tables_selected=[],
            schema_links=[],
            can_proceed=False,
            prompt_preview_chars=0,
        )

    retrieval, links = run_retrieval_validation(
        question=question,
        grounding=grounding,
        chat_intent=chat_intent,
    )
    can_proceed = retrieval.status.value != "insufficient" or not (
        dm_config.DATAMART_VALIDATION_ENFORCE_RETRIEVAL
    )
    return GroundingPreviewResponse(
        question=question,
        retrieval=retrieval,
        tables_selected=list(grounding.table_short_names),
        schema_links=links,
        can_proceed=can_proceed,
        prompt_preview_chars=len(grounding.to_prompt_text()),
    )


def merge_validation(
    retrieval: Optional[RetrievalValidation],
    generation: Optional[GenerationValidation] = None,
    error: Optional[str] = None,
) -> Optional[DatamartValidation]:
    if not dm_config.DATAMART_VALIDATION_ENABLED:
        return None
    ret = retrieval or RetrievalValidation(
        status=ValidationStatus.SUFFICIENT,
        tables_selected=[],
    )
    return build_datamart_validation(
        retrieval=ret,
        generation=generation,
        error=error,
        enforce_retrieval_block=dm_config.DATAMART_VALIDATION_ENFORCE_RETRIEVAL,
    )
