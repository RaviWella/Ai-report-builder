"""Claude Code runner for the AI rule-report chat — one HTTP turn = one fresh
`claude` subprocess (see chat_service.py for why: sessions persist across
requests, a live SDK client does not). The full prior conversation is folded
into the prompt text each turn (same technique support-system's KB chat uses
for stateless multi-turn) rather than kept alive in-process.

``claude-agent-sdk`` is an optional dependency: if it isn't installed, `run()`
raises a clear error — the rest of the report builder is unaffected.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.tenancy import TenantContext
from app.services.ai_datamart_tools import build_datamart_tools
from app.services.rule_report_ai.prompt import build_system_prompt
from app.services.rule_report_ai.schema import build_result_schema


@dataclass
class TurnResult:
    reply: str
    spec: dict | None
    events: list[dict] = field(default_factory=list)
    # Presentation-layer config the AI may optionally propose alongside spec —
    # never part of RuleReportSpec itself (see PivotSpec's docstring).
    row_number_column: str | None = None
    subtotal: dict | None = None
    totals: list[str] = field(default_factory=list)
    pivot: dict | None = None


def _image_block(content: bytes, content_type: str) -> dict:
    media = content_type if content_type.startswith("image/") else "image/png"
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media, "data": base64.b64encode(content).decode()},
    }


def _document_block(content: bytes) -> dict:
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(content).decode()},
    }


def requirement_doc_block(content: bytes, content_type: str, filename: str) -> dict:
    """The requirement-doc attachment as a native multimodal content block —
    highest fidelity for a screenshot/PDF (layout, emphasis, tables), the same
    way a human reads it. `content_type`/`filename` decide image vs PDF."""
    ct = (content_type or "").lower()
    name = (filename or "").lower()
    if ct == "application/pdf" or name.endswith(".pdf"):
        return _document_block(content)
    return _image_block(content, ct)


def _extract_events(message) -> list[dict]:
    out: list[dict] = []
    if message.__class__.__name__ == "AssistantMessage":
        for block in getattr(message, "content", None) or []:
            if block.__class__.__name__ == "TextBlock":
                text = (getattr(block, "text", "") or "").strip()
                if text:
                    out.append({"type": "note", "content": text})
    return out


class RuleReportChatRunner:
    async def run(
        self, *, prompt_text: str, attachment_blocks: list[dict], settings: Settings,
        ctx: TenantContext | None = None, session_id: str = "",
    ) -> TurnResult:
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

        # Give the model safe, read-only, tenant-scoped tools to check the live
        # datamart (does this field exist, what values does it hold) instead of
        # guessing from the static catalogue reference alone — only when ctx is
        # available (every real chat turn has one; ctx=None only in tests).
        mcp_servers: dict = {}
        allowed_tools: list[str] = []
        if ctx is not None:
            tools = build_datamart_tools(ctx, session_id=session_id)
            mcp_servers = {"datamart": create_sdk_mcp_server("datamart", tools=tools)}
            allowed_tools = [f"mcp__datamart__{t.name}" for t in tools]

        options = ClaudeAgentOptions(
            model=settings.rule_ai_model,
            system_prompt=build_system_prompt(),
            allowed_tools=allowed_tools,
            mcp_servers=mcp_servers,
            max_turns=settings.rule_ai_max_turns,
            max_budget_usd=settings.rule_ai_max_budget_usd,
            output_format={"type": "json_schema", "schema": build_result_schema()},
        )

        async def message_stream():
            content: list[dict] = [{"type": "text", "text": prompt_text}]
            content += attachment_blocks
            yield {"type": "user", "message": {"role": "user", "content": content}}

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
            spec=structured.get("spec"),
            events=events,
            row_number_column=structured.get("row_number_column"),
            subtotal=structured.get("subtotal"),
            totals=structured.get("totals") or [],
            pivot=structured.get("pivot"),
        )
