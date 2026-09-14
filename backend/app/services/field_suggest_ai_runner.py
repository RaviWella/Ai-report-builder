"""Single-turn Claude Code SDK runner for the "✨ Suggest matching fields"
button (a column heading that didn't auto-map) — the same read-only,
tenant-scoped datamart tools as the Rule Report chat and Document Studio's
"Smart map" (ai_datamart_tools.py), no persisted session: one request, one
turn, matching this feature's existing one-shot semantics.

Replaces the plain AIProvider.converse() call AIService.suggest_fields() used
to make: same "pick ONE ref from this shortlist, or none" task, now tool-
equipped so an ambiguous heading (e.g. it could plausibly mean either of two
candidate fields) can be resolved by checking the field's real values instead
of guessing from the name alone.
"""

from __future__ import annotations

import os

from app.core.config import Settings
from app.core.tenancy import TenantContext
from app.services.ai_datamart_tools import build_datamart_tools

_SUGGESTION_SCHEMA = {
    "type": "object",
    "properties": {"ref": {"type": ["string", "null"]}},
    "required": ["ref"],
}

_SYSTEM = (
    "You help map a spreadsheet column heading to the correct semantic report "
    "field. You are given a short, pre-ranked shortlist of candidate fields — "
    "choose ONLY a ref from that list, never invent one. You have read-only "
    "tools to check this tenant's own live datamart (list_columns, "
    "sample_distinct_values) — use them when the heading is genuinely "
    "ambiguous between two candidates and checking the field's real values "
    "would resolve it, rather than guessing from the name alone. Reply with "
    "STRICT JSON only, no prose, no code fences."
)


async def suggest_field_sdk(
    ctx: TenantContext, header: str, shortlist_lines: str, settings: Settings,
) -> str | None:
    """Returns the chosen ref, or None if the AI found no good match (or the
    call fails — the caller's deterministic shortlist order stands either way)."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server

    if settings.rule_ai_auth_mode == "subscription":
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("ANTHROPIC_BASE_URL", None)
    else:
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.anthropic_base_url:
            os.environ["ANTHROPIC_BASE_URL"] = settings.anthropic_base_url

    user = (
        f"SPREADSHEET COLUMN HEADING: {header!r}\n\n"
        f"CANDIDATE FIELDS (ref: label — description):\n{shortlist_lines}\n\n"
        "Which ONE ref does this heading most likely mean? If none fit, use null."
    )
    tools = build_datamart_tools(ctx, session_id="suggest-fields")

    options = ClaudeAgentOptions(
        model=settings.rule_ai_model,
        system_prompt=_SYSTEM,
        allowed_tools=[f"mcp__datamart__{t.name}" for t in tools],
        mcp_servers={"datamart": create_sdk_mcp_server("datamart", tools=tools)},
        max_turns=settings.rule_ai_max_turns,
        max_budget_usd=settings.rule_ai_max_budget_usd,
        output_format={"type": "json_schema", "schema": _SUGGESTION_SCHEMA},
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

    if structured is None:
        if error:
            raise RuntimeError(error)
        return None
    ref = structured.get("ref")
    return ref if isinstance(ref, str) and ref else None
