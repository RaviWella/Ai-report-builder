"""Validate schema grounding (retrieval) before LLM SQL generation."""
from __future__ import annotations

import re

from ..orchestration.intent_router import ChatIntent
from ..schema_broker import SchemaGrounding, _tokens_from_text
from ..semantic.semantic_layer import (
    SemanticResolution,
    required_tables_for_question,
)
from .validation_models import RetrievalValidation, SchemaLink, ValidationStatus


def _score_table_relevance(table_short: str, question: str, semantics: SemanticResolution) -> int:
    tokens = _tokens_from_text(question)
    tl = table_short.lower()
    score = sum(2 for tok in tokens if tok in tl)
    if table_short in semantics.seed_tables:
        score += 5
    return score


def validate_retrieval(
    *,
    question: str,
    grounding: SchemaGrounding,
    semantics: SemanticResolution,
    schema_links: list[SchemaLink],
    chat_intent: ChatIntent,
) -> RetrievalValidation:
    selected = [t.lower() for t in grounding.table_short_names]
    warnings: list[str] = []
    clarification: list[str] = []
    missing: list[str] = []

    required = required_tables_for_question(
        question,
        grounded_short_names=grounding.table_short_names,
        chat_intent=chat_intent,
    )
    selected_short = {s.lower() for s in grounding.table_short_names}
    for req in sorted(required):
        if req not in selected_short:
            missing.append(req)

    for link in schema_links:
        if link.confidence == "low" and link.qualified_column:
            warnings.append(
                f"Catalog maps '{link.term}' to {link.qualified_column}, "
                "but that column is not in the grounded allowlist (possible catalog drift)."
            )

    extra_tables: list[str] = []
    for short in grounding.table_short_names:
        if _score_table_relevance(short, question, semantics) == 0 and short.lower() not in required:
            extra_tables.append(short)
    if extra_tables:
        warnings.append(
            "These tables may be irrelevant noise: " + ", ".join(extra_tables) + "."
        )

    q_lower = question.lower()
    if "company" in q_lower and "branch" not in q_lower:
        if "company" in semantics.dimensions_matched and "branch" in semantics.dimensions_matched:
            clarification.append(
                "Did you mean legal entity (company) or branch? Both terms appear relevant."
            )

    status = ValidationStatus.SUFFICIENT
    message: str | None = None

    if not grounding.columns_by_table:
        status = ValidationStatus.INSUFFICIENT
        message = "No schema columns could be loaded for this question."
    elif missing:
        status = ValidationStatus.INSUFFICIENT
        message = (
            "Grounded schema is missing tables expected for this question: "
            + ", ".join(missing)
            + "."
        )
    elif clarification:
        status = ValidationStatus.AMBIGUOUS
        message = " ".join(clarification)
    elif not semantics.topics_matched and not semantics.metrics_matched and not schema_links:
        if chat_intent == ChatIntent.NEW_QUERY and len(selected) <= 1:
            status = ValidationStatus.AMBIGUOUS
            message = (
                "Could not map this question to catalog topics or metrics. "
                "Results may rely on keyword table search only."
            )

    if re.search(r"\b(payroll|salary|leave|attendance|recruitment)\b", q_lower):
        domain_hits = [
            t
            for t in semantics.topics_matched
            if any(k in t for k in ("payroll", "leave", "attendance", "recruitment"))
        ]
        if len(domain_hits) >= 2:
            warnings.append(
                "Multiple HR domains detected in catalog (" + ", ".join(domain_hits) + "). "
                "Confirm the question scope if results look broad."
            )

    return RetrievalValidation(
        status=status,
        source=grounding.source,
        tables_selected=list(grounding.table_short_names),
        topics_matched=list(semantics.topics_matched),
        metrics_matched=list(semantics.metrics_matched),
        schema_links=schema_links,
        missing_tables=missing,
        extra_tables=extra_tables,
        warnings=warnings,
        clarification_hints=clarification,
        message=message,
    )
