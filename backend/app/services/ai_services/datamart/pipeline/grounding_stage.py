"""Deprecated — use ``schema_link_stage.link_schema_for_turn``."""
from __future__ import annotations

from ..schema_broker import SchemaGrounding
from .schema_link_stage import SchemaLinkInput, SchemaLinkResult, link_schema_for_turn

# Backward-compatible aliases
GroundingInput = SchemaLinkInput


def build_turn_grounding(inp: SchemaLinkInput) -> SchemaGrounding:
    return link_schema_for_turn(inp).grounding


def link_schema(inp: SchemaLinkInput) -> SchemaLinkResult:
    return link_schema_for_turn(inp)
