"""Compute overall trust level from retrieval and generation validation."""
from __future__ import annotations

from typing import Optional

from .validation_models import (
    DatamartValidation,
    GenerationValidation,
    RetrievalValidation,
    TrustLevel,
    ValidationStatus,
)


def compute_trust_level(
    *,
    retrieval: RetrievalValidation,
    generation: Optional[GenerationValidation],
    error: Optional[str] = None,
    enforce_retrieval_block: bool = False,
) -> TrustLevel:
    if error:
        return TrustLevel.BLOCKED
    if enforce_retrieval_block and retrieval.status == ValidationStatus.INSUFFICIENT:
        return TrustLevel.BLOCKED
    if generation and generation.binding == "failed":
        return TrustLevel.BLOCKED

    if retrieval.status == ValidationStatus.INSUFFICIENT:
        return TrustLevel.NEEDS_REVIEW
    if retrieval.status == ValidationStatus.AMBIGUOUS:
        return TrustLevel.NEEDS_REVIEW

    if generation:
        if generation.truncated or generation.grounding_expanded:
            return TrustLevel.NEEDS_REVIEW
        if generation.warnings:
            return TrustLevel.NEEDS_REVIEW

    if retrieval.warnings or retrieval.missing_tables:
        return TrustLevel.NEEDS_REVIEW

    if (
        retrieval.status == ValidationStatus.SUFFICIENT
        and generation
        and generation.binding == "passed"
        and not generation.warnings
        and not generation.truncated
        and not generation.grounding_expanded
        and not retrieval.warnings
    ):
        return TrustLevel.VERIFIED

    if generation and generation.binding == "passed":
        return TrustLevel.PLAUSIBLE

    return TrustLevel.PLAUSIBLE


_TRUST_RANK = {
    TrustLevel.BLOCKED: 0,
    TrustLevel.NEEDS_REVIEW: 1,
    TrustLevel.PLAUSIBLE: 2,
    TrustLevel.VERIFIED: 3,
}


def worst_trust_level(*levels: TrustLevel) -> TrustLevel:
    if not levels:
        return TrustLevel.PLAUSIBLE
    return min(levels, key=lambda lv: _TRUST_RANK[lv])


def downgrade_overall_for_blocks(
    validation: DatamartValidation,
    block_levels: list[TrustLevel],
) -> DatamartValidation:
    if not block_levels:
        return validation
    overall = worst_trust_level(validation.overall, *block_levels)
    if overall == validation.overall:
        return validation
    return validation.model_copy(update={"overall": overall})


def build_datamart_validation(
    *,
    retrieval: RetrievalValidation,
    generation: Optional[GenerationValidation] = None,
    error: Optional[str] = None,
    enforce_retrieval_block: bool = False,
) -> DatamartValidation:
    overall = compute_trust_level(
        retrieval=retrieval,
        generation=generation,
        error=error,
        enforce_retrieval_block=enforce_retrieval_block,
    )
    return DatamartValidation(
        retrieval=retrieval,
        generation=generation,
        overall=overall,
    )
