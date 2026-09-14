"""Map business terms from the semantic catalog to physical columns."""
from __future__ import annotations

from ..schema_broker import SchemaGrounding
from ..semantic.semantic_layer import (
    SemanticResolution,
    _load_catalog,
    _match_dimensions,
    _match_metrics,
    _question_tokens,
    _semantic_schema_prefix,
)
from ..validation.validation_models import SchemaLink


def build_schema_links(
    question: str,
    semantics: SemanticResolution,
    grounding: SchemaGrounding,
) -> list[SchemaLink]:
    """Build schema links from catalog dimensions and matched metrics."""
    allowed = grounding.allowlist_qualified_columns()
    tokens = _question_tokens(question)
    links: list[SchemaLink] = []
    seen: set[str] = set()

    for dim_name, table, column in _match_dimensions(question, tokens):
        schema = _semantic_schema_prefix(table)
        qualified = f"{schema}.{table}.{column}".lower()
        if qualified in seen:
            continue
        seen.add(qualified)
        if qualified not in allowed:
            continue
        links.append(
            SchemaLink(
                term=dim_name.replace("_", " "),
                qualified_column=f"{schema}.{table}.{column}",
                confidence="high",
                source="catalog_dimension",
            )
        )

    catalog = _load_catalog()
    metrics_block: dict = catalog.get("metrics") or {}
    for metric_name, _spec in _match_metrics(question, tokens):
        if metric_name in seen:
            continue
        seen.add(metric_name)
        spec = metrics_block.get(metric_name) or {}
        desc = str(spec.get("description") or metric_name.replace("_", " "))
        links.append(
            SchemaLink(
                term=metric_name.replace("_", " "),
                qualified_column="",
                confidence="medium",
                source="catalog_metric",
            )
        )
        # Re-use term field for metric label; qualified_column empty for metrics

    return links[:24]


def link_qualified_columns_used_in_sql(sql: str, links: list[SchemaLink]) -> set[str]:
    """Return qualified columns (lowercase) from links that appear in SQL text."""
    sql_lower = sql.lower()
    used: set[str] = set()
    for link in links:
        if not link.qualified_column:
            continue
        col = link.qualified_column.rsplit(".", 1)[-1].lower()
        if col and col in sql_lower:
            used.add(link.qualified_column.lower())
    return used
