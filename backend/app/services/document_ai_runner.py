"""Single-turn Claude Code SDK runner for Document Studio's "Smart map with
AI" — the same read-only, tenant-scoped datamart tools as the Rule Report
chat (ai_datamart_tools.py), but no persisted conversation/session: one HTTP
request, one turn, matching this feature's existing one-shot semantics.

Reuses extract_letter's exact prompt text (app/ai/base.py) — this is a
mechanism swap (plain Anthropic Messages API -> Claude Code SDK with tools),
not a redesign of the feature's own instructions. Its own prompt says "if
unsure of a field, still list the value with ref null" — tool access gives
the model a real alternative to that: check the live data first.
"""

from __future__ import annotations

import json
import os

from app.ai.base import FieldMetadata, build_extract_letter_prompt
from app.core.config import Settings
from app.core.tenancy import TenantContext
from app.services.ai_datamart_tools import build_datamart_tools

_REPLACEMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "replacements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "ref": {"type": ["string", "null"]},
                },
                "required": ["text", "ref"],
            },
        },
    },
    "required": ["replacements"],
}


async def extract_letter_replacements_sdk(
    ctx: TenantContext, text: str, fields: list[FieldMetadata], settings: Settings,
) -> str:
    """Same contract as AIProvider.extract_letter(): returns a JSON string the
    caller (AIService.extract_letter_replacements) parses exactly as before.
    Tool-equipped: the model can verify a field/value against the live
    datamart before deciding a ref doesn't fit, instead of defaulting to null."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server

    if settings.rule_ai_auth_mode == "subscription":
        # The CLI's own login (a Max plan on the backend host) is the credential;
        # a present ANTHROPIC_API_KEY would override it and bill the key instead.
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("ANTHROPIC_BASE_URL", None)
    else:
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.anthropic_base_url:
            os.environ["ANTHROPIC_BASE_URL"] = settings.anthropic_base_url

    system, user = build_extract_letter_prompt(text, fields)
    tools = build_datamart_tools(ctx, session_id="document-ai-enhance")

    options = ClaudeAgentOptions(
        model=settings.rule_ai_model,
        system_prompt=system,
        allowed_tools=[f"mcp__datamart__{t.name}" for t in tools],
        mcp_servers={"datamart": create_sdk_mcp_server("datamart", tools=tools)},
        max_turns=settings.rule_ai_max_turns,
        max_budget_usd=settings.rule_ai_max_budget_usd,
        output_format={"type": "json_schema", "schema": _REPLACEMENTS_SCHEMA},
    )

    structured: dict | None = None
    error: str | None = None
    async with ClaudeSDKClient(options) as client:
        await client.query(user)
        async for message in client.receive_response():
            so = getattr(message, "structured_output", None)
            if so:
                structured = so
            if message.__class__.__name__ == "ResultMessage" and getattr(message, "is_error", False):
                error = (
                    getattr(message, "result", None)
                    or "; ".join(getattr(message, "errors", None) or [])
                    or f"Claude Code run failed ({getattr(message, 'subtype', 'unknown')})"
                )

    if structured is None and error:
        raise RuntimeError(error)
    return json.dumps(structured or {"replacements": []})
