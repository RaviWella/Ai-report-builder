"""Pydantic models for datamart retrieval and generation validation."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(str, Enum):
    SUFFICIENT = "sufficient"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT = "insufficient"


class TrustLevel(str, Enum):
    VERIFIED = "verified"
    PLAUSIBLE = "plausible"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class SchemaLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    qualified_column: str
    confidence: Literal["high", "medium", "low"]
    source: Literal["catalog_dimension", "catalog_metric", "inferred"]


class RetrievalValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ValidationStatus
    source: str = ""
    tables_selected: list[str] = Field(default_factory=list)
    topics_matched: list[str] = Field(default_factory=list)
    metrics_matched: list[str] = Field(default_factory=list)
    schema_links: list[SchemaLink] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)
    extra_tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarification_hints: list[str] = Field(default_factory=list)
    message: Optional[str] = None
    columns_in_context: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Per-table column names sent to the LLM (join keys suffixed with *).",
    )


class GenerationValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding: Literal["passed", "failed", "skipped"] = "skipped"
    warnings: list[str] = Field(default_factory=list)
    truncated: bool = False
    grounding_expanded: bool = False
    evidence: Optional[dict[str, Any]] = None


class DatamartValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval: RetrievalValidation
    generation: Optional[GenerationValidation] = None
    overall: TrustLevel
    awaiting_clarification: bool = False
    anchor_question: Optional[str] = Field(
        default=None,
        description="Original user question when the assistant is asking for clarification.",
    )
