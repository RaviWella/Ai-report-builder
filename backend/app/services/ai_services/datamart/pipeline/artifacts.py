"""Pipeline data contracts (S2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..schema_broker import SchemaGrounding


@dataclass
class QueryPlan:
    """Structured plan produced before Tier-C SQL generation."""

    tables: list[str] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    select_columns: list[str] = field(default_factory=list)
    aggregations: Optional[dict[str, Any]] = None
    order_limit: str = ""
    raw_json: str = ""

    def to_prompt_block(self) -> str:
        lines = ["QUERY PLAN (execute exactly; use only listed tables):"]
        if self.tables:
            lines.append(f"Tables: {', '.join(self.tables)}")
        if self.joins:
            lines.append("Joins:")
            lines.extend(f"  - {j}" for j in self.joins)
        if self.filters:
            lines.append("Filters:")
            lines.extend(f"  - {f}" for f in self.filters)
        if self.select_columns:
            lines.append(f"SELECT: {', '.join(self.select_columns)}")
        if self.aggregations:
            lines.append(f"Aggregations: {self.aggregations}")
        if self.order_limit:
            lines.append(self.order_limit)
        return "\n".join(lines)


@dataclass
class SqlArtifact:
    sql: Optional[str]
    narrative: str
    post_process_config: Optional[list]
    source: Optional[str]
    tier: str  # A | B | C
    llm_output: str = ""
    query_plan: Optional[QueryPlan] = None
    grounding: Optional[SchemaGrounding] = None
    catalog_governed: bool = False
    use_verified_metric: bool = False
    needs_clarification: bool = False
    clarification_message: str = ""


@dataclass
class VerifyResult:
    passed: bool
    sql: str
    narrative: str
    post_process_config: Optional[list]
    grounding: SchemaGrounding
    detail: str
    errors: list[str] = field(default_factory=list)
    blocked: bool = False
