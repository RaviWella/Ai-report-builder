"""Shared validation state and response finalization for chat/template pipelines."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .. import config as dm_config
from ..schema_broker import SchemaGrounding
from .trust_scorer import TrustLevel, downgrade_overall_for_blocks
from ..domain_sql.report_spec import ReportSpec
from .validation_models import GenerationValidation, RetrievalValidation
from .validation_context import enrich_retrieval_with_grounding
from .validation_runner import (
    attach_validation_to_response,
    run_generation_validation,
)
from ..models import DatamartResponse
from ..schema_broker import SchemaGrounding


@dataclass
class PipelineValidationState:
    """Carries retrieval context through a pipeline run for consistent validation attachment."""

    question: str
    retrieval: Optional[RetrievalValidation] = None
    schema_links: list = field(default_factory=list)
    report_spec: Optional[ReportSpec] = None
    block_trust_levels: list[TrustLevel] = field(default_factory=list)
    grounding_expanded: bool = False

    def finish(
        self,
        response: DatamartResponse,
        *,
        sql: Optional[str] = None,
        grounding: Optional[SchemaGrounding] = None,
        binding_passed: bool = True,
        row_count: int = 0,
        generation: Optional[GenerationValidation] = None,
        run_critic: bool = True,
        awaiting_clarification: bool = False,
    ) -> DatamartResponse:
        retrieval = self.retrieval
        if retrieval and grounding:
            retrieval = enrich_retrieval_with_grounding(retrieval, grounding)
        gen = generation
        if gen is None and dm_config.DATAMART_VALIDATION_ENABLED and sql and grounding:
            gen = run_generation_validation(
                question=self.question,
                sql=sql,
                grounding=grounding,
                schema_links=self.schema_links,
                binding_passed=binding_passed,
                row_count=row_count,
                grounding_expanded=self.grounding_expanded,
                run_critic=run_critic and dm_config.DATAMART_VALIDATION_CRITIC,
            )
        out = attach_validation_to_response(
            response,
            retrieval,
            generation=gen,
        )
        if out.validation and awaiting_clarification:
            out = out.model_copy(
                update={
                    "validation": out.validation.model_copy(
                        update={
                            "awaiting_clarification": True,
                            "anchor_question": self.question,
                        }
                    )
                }
            )
        if out.validation and self.block_trust_levels:
            merged = downgrade_overall_for_blocks(
                out.validation,
                self.block_trust_levels,
            )
            out = out.model_copy(update={"validation": merged})
        return out


def finish_validated_response(
    pval: PipelineValidationState,
    resp: DatamartResponse,
    *,
    sql: Optional[str] = None,
    grounding: Optional[SchemaGrounding] = None,
    binding_passed: bool = True,
    row_count: int = 0,
    generation: Optional[GenerationValidation] = None,
    run_critic: bool = True,
    awaiting_clarification: bool = False,
) -> DatamartResponse:
    """Attach retrieval/generation validation to any pipeline exit (chat or template)."""
    return pval.finish(
        resp,
        sql=sql if sql is not None else resp.sql,
        grounding=grounding,
        binding_passed=binding_passed,
        row_count=row_count or resp.row_count or 0,
        generation=generation,
        run_critic=run_critic,
        awaiting_clarification=awaiting_clarification,
    )
