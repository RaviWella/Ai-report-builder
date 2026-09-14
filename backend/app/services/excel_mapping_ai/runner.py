"""Claude Code runner for the Excel-mapping chat — one HTTP turn = one fresh
`claude` subprocess, same technique as `rule_report_ai/runner.py` (see its
docstring for why), trimmed down: no datamart MCP tools (the given field
catalogue is enough context — no live datamart lookups needed) and no
attachments (nothing is uploaded mid-chat here).

``claude-agent-sdk`` is an optional dependency: if it isn't installed, `run()`
raises a clear error — the rest of the report builder is unaffected.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.core.config import Settings
from app.services.excel_mapping_ai.prompt import build_system_prompt
from app.services.excel_mapping_ai.schema import build_result_schema


@dataclass
class TurnResult:
    reply: str
    mappings: list[dict] | None
    events: list[dict] = field(default_factory=list)


def _extract_events(message) -> list[dict]:
    out: list[dict] = []
    if message.__class__.__name__ == "AssistantMessage":
        for block in getattr(message, "content", None) or []:
            if block.__class__.__name__ == "TextBlock":
                text = (getattr(block, "text", "") or "").strip()
                if text:
                    out.append({"type": "note", "content": text})
    return out


class ExcelMappingChatRunner:
    async def run(self, *, prompt_text: str, settings: Settings) -> TurnResult:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

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

        options = ClaudeAgentOptions(
            model=settings.rule_ai_model,
            system_prompt=build_system_prompt(),
            max_turns=settings.rule_ai_max_turns,
            max_budget_usd=settings.rule_ai_max_budget_usd,
            output_format={"type": "json_schema", "schema": build_result_schema()},
        )

        async def message_stream():
            yield {"type": "user", "message": {"role": "user", "content": prompt_text}}

        events: list[dict] = []
        structured: dict | None = None
        error: str | None = None
        async with ClaudeSDKClient(options) as client:
            await client.query(message_stream())
            async for message in client.receive_response():
                events.extend(_extract_events(message))
                so = getattr(message, "structured_output", None)
                if so:
                    structured = so
                if message.__class__.__name__ == "ResultMessage" and getattr(message, "is_error", False):
                    error = (
                        getattr(message, "result", None)
                        or "; ".join(getattr(message, "errors", None) or [])
                        or f"Claude Code run failed ({getattr(message, 'subtype', 'unknown')})"
                    )

        # A CLI/auth/budget failure ends the turn with no structured_output — don't
        # silently return a fake "(no reply)"; the caller needs to know this failed.
        if structured is None and error:
            raise RuntimeError(error)

        structured = structured or {}
        return TurnResult(
            reply=structured.get("reply") or "(no reply)",
            mappings=structured.get("mappings"),
            events=events,
        )
