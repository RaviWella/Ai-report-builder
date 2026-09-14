"""Legacy SQL Converter — a standalone migration helper, isolated from the
Rule Report chat/DSL engine. Turns an old source-DB report query into a
business-logic document; the implementer copies that document into the
existing AI Rule Report chat as a requirement. See
app/services/legacy_sql_converter/__init__.py for why this is deliberately
separate from the generic chat.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.crypto import SecretError
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.services.legacy_sql_converter import converter_service

router = APIRouter(
    prefix="/legacy-sql", tags=["legacy-sql"], dependencies=[Depends(require_roles(*BuilderRoles))]
)


class AnalyzeBody(BaseModel):
    sql: str


class AnalyzeResult(BaseModel):
    document: str


@router.post("/analyze", response_model=AnalyzeResult)
async def analyze(
    body: AnalyzeBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> AnalyzeResult:
    if not body.sql.strip():
        raise HTTPException(status_code=400, detail="Paste the legacy SQL to analyze")
    try:
        document = await converter_service.analyze(db, ctx, body.sql)
    except SecretError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"Legacy SQL Converter is not available on this server: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Claude Code run failed: {exc}") from exc
    return AnalyzeResult(document=document)
