"""Orchestrates one AI rule-report chat turn: fold the session's transcript +
attachments into a prompt, call the Claude Code runner, VALIDATE any `spec` it
returns before trusting it (retrying once with the exact error on failure —
never surfacing a bare exception), and persist the turn.

Reuses ChatHistoryService for session create/list/get/rename/delete; this
service only adds the turn-with-attachments-and-AI-call behaviour specific to
the rule-report builder.
"""

from __future__ import annotations

import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.core.tenancy import TenantContext
from app.db.metadata import AISession, AISessionAttachment
from app.domain.report_spec import PivotSpec
from app.ingestion.document_parser import parse_document
from app.services.chat_history import ChatHistoryService
from app.services.rule_report_ai.catalogue import build_catalogue_reference
from app.services.rule_report_ai.runner import (
    RuleReportChatRunner,
    TurnResult,
    requirement_doc_block,
)
from app.services.rule_report_ai.spec_validation import validate_spec

_SQL_DECODE_ERRORS = "replace"  # a source SQL file is business logic, not user-facing text


class RuleReportChatService:
    def __init__(self, db: Session, runner: RuleReportChatRunner | None = None):
        self.db = db
        self.history = ChatHistoryService(db)
        self.runner = runner or RuleReportChatRunner()

    def create(self, ctx: TenantContext, title: str | None = None) -> dict:
        return self.history.create(ctx, title, kind="rule_report")

    def list(self, ctx: TenantContext) -> list[dict]:
        return self.history.list(ctx, kind="rule_report")

    def get(self, ctx: TenantContext, session_id: str) -> dict | None:
        return self.history.get(ctx, session_id)

    def delete(self, ctx: TenantContext, session_id: str) -> bool:
        return self.history.delete(ctx, session_id)

    async def send_message(
        self,
        ctx: TenantContext,
        session_id: str,
        message: str,
        requirement_doc: tuple[bytes, str, str] | None = None,  # (content, filename, content_type)
        sample_sheet: tuple[bytes, str, str] | None = None,
        source_sql: tuple[bytes, str, str] | None = None,
    ) -> dict:
        s = self.history.find(ctx, session_id)
        if s is None or s.kind != "rule_report":
            raise ValueError("Rule report chat session not found")

        attachments_meta: list[dict] = []
        if requirement_doc is not None:
            content, filename, content_type = requirement_doc
            self._store_requirement_doc(session_id, content, filename, content_type)
            attachments_meta.append({"kind": "requirement_doc", "filename": filename})
        if sample_sheet is not None:
            content, filename, content_type = sample_sheet
            parsed = parse_document(content, filename=filename, content_type=content_type)
            s.sample_sheet_headers = [
                {"header": c.header, "type": c.inferred_type} for c in parsed.columns
            ]
            s.sample_sheet_filename = filename
            attachments_meta.append({"kind": "sample_sheet", "filename": filename})
        if source_sql is not None:
            content, filename, _content_type = source_sql
            s.source_sql = content.decode("utf-8", errors=_SQL_DECODE_ERRORS)
            s.source_sql_filename = filename
            attachments_meta.append({"kind": "source_sql", "filename": filename})

        settings = get_settings()
        doc_block = self._requirement_doc_block(session_id)
        attachment_blocks = [doc_block] if doc_block else []
        schema_reference = build_catalogue_reference(self.db, ctx.tenant_id)

        prompt_text = _build_prompt_text(s, message, schema_reference)
        turn = await self._run_and_validate(
            prompt_text, attachment_blocks, settings, ctx=ctx, session_id=session_id,
        )

        turn_messages = [
            {"role": "you", "text": message, "attachments": attachments_meta},
            {
                "role": "assistant", "text": turn.reply, "spec": turn.spec,
                "row_number_column": turn.row_number_column, "subtotal": turn.subtotal,
                "totals": turn.totals, "pivot": turn.pivot,
            },
        ]
        head = self.history.append(
            ctx, session_id, turn_messages,
            working_rule_spec=turn.spec if turn.spec is not None else None,
        )
        return {
            **(head or {}), "reply": turn.reply, "spec": turn.spec,
            "row_number_column": turn.row_number_column, "subtotal": turn.subtotal,
            "totals": turn.totals, "pivot": turn.pivot,
        }

    async def _run_and_validate(
        self, prompt_text: str, attachment_blocks: list[dict], settings: Settings,
        *, ctx: TenantContext, session_id: str,
    ) -> TurnResult:
        """Call the runner; validate any `spec`/`pivot` it returns before trusting
        them (never the raw AI JSON) and retry ONCE with the exact error on
        failure. Pure w.r.t. self.db — only touches self.runner — so this is
        unit-testable with a fake runner and no database (ctx is just data, no
        DB access here). Returns a TurnResult with spec/pivot replaced by their
        VALIDATED dumps (or None)."""
        result = await self.runner.run(
            prompt_text=prompt_text, attachment_blocks=attachment_blocks, settings=settings,
            ctx=ctx, session_id=session_id,
        )
        spec_dict, pivot_dict, validation_error = _validated_turn(result)
        if validation_error is not None:
            result = await self._retry_after_validation_error(
                prompt_text, attachment_blocks, validation_error, settings,
                ctx=ctx, session_id=session_id,
            )
            if result.spec is not None or result.pivot is not None:
                spec_dict, pivot_dict, validation_error = _validated_turn(result)
            else:
                # The AI chose to ask a clarifying question instead of retrying
                # blind — its own (new) reply already covers why, so don't also
                # tack on the now-stale first error.
                spec_dict, pivot_dict, validation_error = None, None, None

        reply = result.reply
        if validation_error is not None:
            reply = (
                f"{reply}\n\n(The report definition I produced didn't quite validate: "
                f"{validation_error}. Tell me more so I can fix it.)"
            )
        return TurnResult(
            reply=reply, spec=spec_dict, pivot=pivot_dict,
            row_number_column=result.row_number_column, subtotal=result.subtotal,
            totals=result.totals,
        )

    async def _retry_after_validation_error(
        self, prompt_text: str, attachment_blocks: list[dict], error: str, settings: Settings,
        *, ctx: TenantContext, session_id: str,
    ) -> TurnResult:
        corrective = (
            f"{prompt_text}\n\n---\nThe `spec` you just produced FAILED validation with this "
            f"exact error:\n  {error}\nFix ONLY what's needed to resolve this error and return "
            f"the corrected `spec` (or null plus a `reply` asking what you're missing, if you "
            f"can't fix it from what you know)."
        )
        return await self.runner.run(
            prompt_text=corrective, attachment_blocks=attachment_blocks, settings=settings,
            ctx=ctx, session_id=session_id,
        )

    def _store_requirement_doc(self, session_id: str, content: bytes, filename: str, content_type: str) -> None:
        self.db.execute(delete(AISessionAttachment).where(AISessionAttachment.session_id == session_id))
        self.db.add(AISessionAttachment(
            session_id=session_id,
            filename=filename,
            content_type=content_type or "application/octet-stream",
            content_enc=encrypt_bytes(content),
            size_bytes=len(content),
        ))
        self.db.flush()

    def _requirement_doc_block(self, session_id: str) -> dict | None:
        att = self.db.get(AISessionAttachment, session_id)
        if att is None:
            return None
        content = decrypt_bytes(att.content_enc)
        return requirement_doc_block(content, att.content_type, att.filename)


def _validated_dict(raw_spec: dict) -> tuple[dict | None, str | None]:
    spec, error = validate_spec(raw_spec)
    if error is not None:
        return None, error
    return spec.model_dump(mode="json", by_alias=True, exclude_defaults=True), None


def _validated_pivot_dict(raw_pivot: dict) -> tuple[dict | None, str | None]:
    try:
        pivot = PivotSpec.model_validate(raw_pivot)
    except Exception as exc:  # noqa: BLE001 - surfaced as a normal retry-turn error, not a crash
        return None, str(exc)
    return pivot.model_dump(mode="json", exclude_defaults=True), None


def _validated_turn(result: TurnResult) -> tuple[dict | None, dict | None, str | None]:
    """Validate a turn's spec AND pivot (either optional) — the first failure
    (spec checked before pivot) becomes the one error the retry turn is told
    about, matching the existing single-error-per-retry contract."""
    spec_dict: dict | None = None
    pivot_dict: dict | None = None
    if result.spec is not None:
        spec_dict, error = _validated_dict(result.spec)
        if error is not None:
            return None, None, error
    if result.pivot is not None:
        pivot_dict, error = _validated_pivot_dict(result.pivot)
        if error is not None:
            return spec_dict, None, error
    return spec_dict, pivot_dict, None


def _build_prompt_text(session: AISession, new_message: str, schema_reference: str = "") -> str:
    parts: list[str] = []
    if schema_reference:
        parts.append(schema_reference)
    for m in session.messages or []:
        role = "Analyst" if m.get("role") == "you" else "You (assistant, prior turn)"
        text = m.get("text") or ""
        if text:
            parts.append(f"{role}: {text}")
    if session.sample_sheet_headers:
        parts.append(
            "Sample output sheet headers uploaded by the analyst (headers/types "
            "only — the underlying data was never sent to you):\n"
            + json.dumps(session.sample_sheet_headers, indent=2)
        )
    if session.source_sql:
        parts.append(
            "LEGACY source SQL the analyst uploaded (the report this is replacing, "
            "read from the OLD source database — NOT the new datamart). Use it to "
            "understand the business logic, then map its tables/columns to the "
            "physical reference above. Never assume the legacy table/column names "
            "exist in the new datamart.\n```sql\n" + session.source_sql + "\n```"
        )
    if session.working_rule_spec:
        parts.append(
            "The current draft spec (refine this unless the analyst is asking for "
            "something new):\n```json\n" + json.dumps(session.working_rule_spec, indent=2) + "\n```"
        )
    parts.append(f"Analyst (new message): {new_message}")
    return "\n\n".join(parts)
