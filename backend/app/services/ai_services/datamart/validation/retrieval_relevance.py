"""Post-filter grounded tables by keyword/semantic relevance (reduces noise).

Deprecated: S1 ``schema_link_stage`` + domain allowlist replaced this in the chat
pipeline. Retained for regression tests only; not called from ``runner.py``.
"""
from __future__ import annotations

from ..schema_broker import SchemaGrounding, _tokens_from_text
from ..semantic.semantic_layer import SemanticResolution, required_tables_for_question


def apply_retrieval_relevance_filter(
    *,
    question: str,
    grounding: SchemaGrounding,
    semantics: SemanticResolution,
    max_tables: int,
) -> SchemaGrounding:
    """
    Re-rank and trim ``grounding.columns_by_table`` to drop likely-irrelevant tables.

    Keeps all seed tables and any table with a positive keyword score.
    """
    if not grounding.columns_by_table:
        return grounding

    seeds = {t.lower() for t in semantics.seed_tables}
    required = required_tables_for_question(
        question,
        grounded_short_names=grounding.table_short_names,
    )
    scored: list[tuple[int, str]] = []
    for qualified in grounding.columns_by_table:
        short = qualified.rsplit(".", 1)[-1]
        score = 0
        if short.lower() in required:
            score += 100
        if short.lower() in seeds:
            score += 10
        tokens = _tokens_from_text(question)
        tl = short.lower()
        score += sum(2 for tok in tokens if tok in tl)
        score += sum(1 for tok in tokens if tok in tl.split("_"))
        if score > 0 or short.lower() in seeds:
            scored.append((score, short))

    if not scored:
        return grounding

    scored.sort(key=lambda x: (-x[0], x[1]))
    keep_shorts = [s for _, s in scored[:max_tables]]
    if not keep_shorts:
        return grounding

    new_map = {
        q: cols
        for q, cols in grounding.columns_by_table.items()
        if q.rsplit(".", 1)[-1].lower() in {k.lower() for k in keep_shorts}
    }
    if len(new_map) == len(grounding.columns_by_table):
        return grounding

    return SchemaGrounding(
        columns_by_table=new_map,
        join_hint_lines=list(grounding.join_hint_lines),
        semantic_prompt_block=grounding.semantic_prompt_block,
        dimension_bindings=list(grounding.dimension_bindings),
        topics_matched=list(grounding.topics_matched),
        metrics_matched=list(grounding.metrics_matched),
        source=grounding.source + "+relevance_filter",
    )
