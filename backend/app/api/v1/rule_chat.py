"""AI-assisted Rule Report chat — upload a requirement doc + sample sheet and
iterate with Claude Code to a validated RuleReportSpec JSON, replacing the
manual "hand-write the JSON, paste it in" workflow (see rule-report/explain
and the builder's "JSON logic" tab this feeds into).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.crypto import SecretError
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.services.rule_report_ai.chat_service import RuleReportChatService

router = APIRouter(
    prefix="/ai/rule-chat", tags=["ai"], dependencies=[Depends(require_roles(*BuilderRoles))]
)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB, matches the source-file upload cap


class SessionCreate(BaseModel):
    title: str | None = None


@router.post("/sessions")
def create_session(
    body: SessionCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return RuleReportChatService(db).create(ctx, body.title)


@router.get("/sessions")
def list_sessions(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return {"sessions": RuleReportChatService(db).list(ctx)}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    s = RuleReportChatService(db).get(ctx, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return s


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    if not RuleReportChatService(db).delete(ctx, session_id):
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"deleted": True}


async def _read_capped(file: UploadFile) -> bytes:
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    return raw


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    message: str = Form(""),
    requirement_doc: UploadFile | None = File(None),
    sample_sheet: UploadFile | None = File(None),
    source_sql: UploadFile | None = File(None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    req_tuple = None
    if requirement_doc is not None and requirement_doc.filename:
        content = await _read_capped(requirement_doc)
        req_tuple = (content, requirement_doc.filename, requirement_doc.content_type or "")
    sheet_tuple = None
    if sample_sheet is not None and sample_sheet.filename:
        content = await _read_capped(sample_sheet)
        sheet_tuple = (content, sample_sheet.filename, sample_sheet.content_type or "")
    sql_tuple = None
    if source_sql is not None and source_sql.filename:
        content = await _read_capped(source_sql)
        sql_tuple = (content, source_sql.filename, source_sql.content_type or "")

    if not message.strip() and req_tuple is None and sheet_tuple is None and sql_tuple is None:
        raise HTTPException(status_code=400, detail="Send a message or attach a file")

    try:
        return await RuleReportChatService(db).send_message(
            ctx, session_id, message,
            requirement_doc=req_tuple, sample_sheet=sheet_tuple, source_sql=sql_tuple,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SecretError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"AI rule-report chat is not available on this server: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Claude Code run failed: {exc}") from exc
