"""Orchestrates one Legacy SQL Converter analysis: gather this tenant's
schema + legacy-code references, build the prompt, call Claude Code, return
the business-logic document. No session/history persistence — a one-shot
utility (paste SQL in, copy the document out into the Rule Report chat)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenancy import TenantContext
from app.services.legacy_sql_converter import catalogue
from app.services.legacy_sql_converter.runner import run as run_claude


async def analyze(db: Session, ctx: TenantContext, legacy_sql: str) -> str:
    settings = get_settings()
    reference = build_reference(db, ctx)
    prompt_text = build_prompt_text(legacy_sql, reference)
    return await run_claude(prompt_text=prompt_text, settings=settings)


def build_reference(db: Session, ctx: TenantContext) -> str:
    return "\n\n".join(filter(None, [
        catalogue.build_mart_reference(db, ctx.tenant_id),
        catalogue.build_core_schema_reference(ctx),
        catalogue.build_dim_value_reference(ctx),
        catalogue.build_code_dictionary_reference(ctx),
    ]))


def build_prompt_text(legacy_sql: str, reference: str) -> str:
    """Pure, so it's unit-testable without a live DB/Claude call."""
    if not reference:
        return (
            "No schema reference could be gathered for this tenant — note any "
            f"unresolved mapping questions accordingly.\n\nLegacy SQL to analyze:\n"
            f"```sql\n{legacy_sql}\n```"
        )
    return f"{reference}\n\n---\n\nLegacy SQL to analyze:\n```sql\n{legacy_sql}\n```"
