"""Augment retrieval validation with grounded column context for the UI."""
from __future__ import annotations

from ..llm.llm_context_log import grounding_columns_summary
from ..schema_broker import SchemaGrounding
from .validation_models import RetrievalValidation


def enrich_retrieval_with_grounding(
    retrieval: RetrievalValidation,
    grounding: SchemaGrounding,
) -> RetrievalValidation:
    """Attach per-table column lists (SELECT vs join-only marked with *)."""
    if not grounding.columns_by_table:
        return retrieval
    summary = grounding_columns_summary(grounding)
    if not summary:
        return retrieval
    return retrieval.model_copy(update={"columns_in_context": summary})
