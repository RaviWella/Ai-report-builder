"""Claude Code runner for the Legacy SQL Converter — one call in, one document
out. Simpler than the rule-report chat's runner: no multi-turn state, no
`output_format` JSON schema (the output IS the document, plain Markdown
text), no retry-on-validation-failure loop (there's no structured shape to
validate against — the analyst reads the document and judges it themselves).

``claude-agent-sdk`` is an optional dependency: if it isn't installed, `run()`
raises a clear error.
"""

from __future__ import annotations

import os

from app.core.config import Settings
from app.services.legacy_sql_converter.prompt import SYSTEM_PROMPT


async def run(*, prompt_text: str, settings: Settings) -> str:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    if settings.rule_ai_auth_mode == "subscription":
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("ANTHROPIC_BASE_URL", None)
    else:
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.anthropic_base_url:
            os.environ["ANTHROPIC_BASE_URL"] = settings.anthropic_base_url

    options = ClaudeAgentOptions(
        model=settings.rule_ai_model,
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=[],  # pure text generation — no file/bash/tool access
        max_turns=settings.rule_ai_max_turns,
        max_budget_usd=settings.rule_ai_max_budget_usd,
    )

    async def message_stream():
        yield {"type": "user", "message": {"role": "user", "content": prompt_text}}

    text_parts: list[str] = []
    error: str | None = None
    async with ClaudeSDKClient(options) as client:
        await client.query(message_stream())
        async for message in client.receive_response():
            if message.__class__.__name__ == "AssistantMessage":
                for block in getattr(message, "content", None) or []:
                    if block.__class__.__name__ == "TextBlock":
                        text_parts.append(getattr(block, "text", "") or "")
            if message.__class__.__name__ == "ResultMessage" and getattr(message, "is_error", False):
                error = (
                    getattr(message, "result", None)
                    or "; ".join(getattr(message, "errors", None) or [])
                    or f"Claude Code run failed ({getattr(message, 'subtype', 'unknown')})"
                )

    # An is_error ResultMessage always wins, even if some text also came
    # through — a CLI/auth failure (e.g. "Not logged in") is often delivered
    # AS assistant text, not just in the result's error field, and must not
    # be mistaken for a genuine (if short) document.
    if error:
        raise RuntimeError(error)
    return "".join(text_parts).strip()
