"""Orchestrates one Excel-mapping chat turn: fold the session's transcript +
the tenant's field catalogue + the current mapping state into a prompt, call
the Claude Code runner, VALIDATE any `mappings` it returns before trusting it
(retrying once with the exact error on failure), and persist the turn.

Reuses ChatHistoryService for session create/get; this service only adds the
turn-with-catalogue-and-AI-call behaviour specific to Excel-mapping. Unlike
rule_report_ai's chat_service, this one does NOT persist "current mapping
state" on the session (no `working_*` column) — the frontend is the single
source of truth for the review screen's mapping state (the user can freely
edit it between chat turns via the manual picker), so it's resent fresh on
every call instead of risking server/client drift.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.tenancy import TenantContext
from app.db.metadata import AISession
from app.domain.semantic import SemanticCatalog
from app.services.chat_history import ChatHistoryService
from app.services.excel_mapping_ai.mapping_validation import validate_mapping
from app.services.excel_mapping_ai.runner import ExcelMappingChatRunner, TurnResult
from app.services.semantic_service import SemanticService


class ExcelMappingChatService:
    def __init__(self, db: Session, runner: ExcelMappingChatRunner | None = None):
        self.db = db
        self.history = ChatHistoryService(db)
        self.runner = runner or ExcelMappingChatRunner()

    def create(self, ctx: TenantContext, title: str | None = None) -> dict:
        return self.history.create(ctx, title, kind="excel_mapping")

    async def send_message(
        self,
        ctx: TenantContext,
        session_id: str,
        message: str,
        headers: list[str],
        current_mapping: dict[str, str | None],
    ) -> dict:
        s = self.history.find(ctx, session_id)
        if s is None or s.kind != "excel_mapping":
            raise ValueError("Excel-mapping chat session not found")

        catalog = SemanticService(self.db).get_active_catalog(ctx.tenant_id)
        settings = get_settings()

        prompt_text = _build_prompt_text(s, message, catalog.metadata_for_ai(), headers, current_mapping)
        turn = await self._run_and_validate(prompt_text, catalog, headers, settings)

        turn_messages = [
            {"role": "you", "text": message},
            {"role": "assistant", "text": turn.reply, "mappings": turn.mappings},
        ]
        head = self.history.append(ctx, session_id, turn_messages)
        return {**(head or {}), "reply": turn.reply, "mappings": turn.mappings}

    async def _run_and_validate(
        self, prompt_text: str, catalog: SemanticCatalog, headers: list[str], settings: Settings,
    ) -> TurnResult:
        """Call the runner; validate any `mappings` it returns before trusting
        it and retry ONCE with the exact error on failure. Pure w.r.t. self.db
        (only touches self.runner/catalog, both passed in) so this is
        unit-testable with a fake runner and no database."""
        result = await self.runner.run(prompt_text=prompt_text, settings=settings)
        mapping_dict, validation_error = validate_mapping(catalog, headers, result.mappings)
        if validation_error is not None:
            corrective = (
                f"{prompt_text}\n\n---\nThe `mappings` you just produced FAILED "
                f"validation with this exact error:\n  {validation_error}\nFix ONLY "
                f"what's needed to resolve this error and return the corrected "
                f"`mappings` (or null plus a `reply` asking what you're missing, if "
                f"you can't fix it from what you know)."
            )
            result = await self.runner.run(prompt_text=corrective, settings=settings)
            if result.mappings is not None:
                mapping_dict, validation_error = validate_mapping(catalog, headers, result.mappings)
            else:
                # The AI chose to ask a clarifying question instead of retrying
                # blind — its own (new) reply already covers why.
                mapping_dict, validation_error = None, None

        reply = result.reply
        if validation_error is not None:
            reply = (
                f"{reply}\n\n(The mapping I produced didn't quite validate: "
                f"{validation_error}. Tell me more so I can fix it.)"
            )
        return TurnResult(reply=reply, mappings=_as_list(mapping_dict))


def _as_list(mapping_dict: dict[str, str | None] | None) -> list[dict] | None:
    if mapping_dict is None:
        return None
    return [{"header": h, "ref": r} for h, r in mapping_dict.items()]


def _build_prompt_text(
    session: AISession, new_message: str, catalog_fields: list[dict],
    headers: list[str], current_mapping: dict[str, str | None],
) -> str:
    parts: list[str] = [
        "THE FIELD CATALOGUE:\n" + json.dumps(catalog_fields, indent=2),
    ]
    if current_mapping:
        parts.append(
            "ALREADY MAPPED (read-only context — never include these headers "
            "in your `mappings`):\n" + json.dumps(current_mapping, indent=2)
        )
    parts.append("HEADERS TO MAP (only these are valid in your `mappings`):\n" + json.dumps(headers, indent=2))
    for m in session.messages or []:
        role = "Analyst" if m.get("role") == "you" else "You (assistant, prior turn)"
        text = m.get("text") or ""
        if text:
            parts.append(f"{role}: {text}")
    parts.append(f"Analyst (new message): {new_message}")
    return "\n\n".join(parts)
