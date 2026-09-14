"""The Claude Code `output_format` JSON schema for an Excel-mapping chat
turn — much simpler than the rule-chat one (no dynamic-keyed maps, so no
need for its `_relax_dynamic_maps` step): {reply, mappings}. `mappings` is
null until the AI has a proposal for at least one of the given headers."""

from __future__ import annotations


def build_result_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "reply": {
                "type": "string",
                "description": "The conversational message to show the analyst — "
                "what you mapped, or what you still need to know.",
            },
            "mappings": {
                "anyOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "header": {
                                    "type": "string",
                                    "description": "Exact header text, from the "
                                    "'headers to map' list given to you.",
                                },
                                "ref": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "description": "A ref from the given field "
                                    "catalogue, or null if this column shouldn't "
                                    "be imported.",
                                },
                            },
                            "required": ["header", "ref"],
                        },
                    },
                    {"type": "null"},
                ],
                "description": "OPTIONAL: your proposed mapping for one or more "
                "of the still-unmapped headers. Only include headers you're "
                "confident about — leave the rest out and ask in `reply` "
                "instead of guessing. Null while you still need more "
                "information from the analyst.",
            },
        },
        "required": ["reply", "mappings"],
    }
