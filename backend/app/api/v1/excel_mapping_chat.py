"""AI-assisted Excel-mapping chat — finishes mapping the columns
`ExcelUpload.tsx`'s automatic pass couldn't resolve, via a short back-and-
forth instead of one-shot per-header suggestions. See
`app/services/excel_mapping_ai/chat_service.py` for the turn logic.

Deliberately minimal: create + send-message only — nothing in the UI needs
to browse mapping-chat history separately from the upload review screen
it's embedded in (unlike the rule-report chat, which a saved report links
back to and resumes later).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.crypto import SecretError
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.services.excel_mapping_ai.chat_service import ExcelMappingChatService

router = APIRouter(
    prefix="/ai/excel-mapping-chat", tags=["ai"], dependencies=[Depends(require_roles(*BuilderRoles))]
)


class SessionCreate(BaseModel):
    title: str | None = None


@router.post("/sessions")
def create_session(
    body: SessionCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return ExcelMappingChatService(db).create(ctx, body.title)


class MessageBody(BaseModel):
    message: str = ""
    headers: list[str] = []
    current_mapping: dict[str, str | None] = {}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: MessageBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Send a message")
    try:
        return await ExcelMappingChatService(db).send_message(
            ctx, session_id, body.message, body.headers, body.current_mapping,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SecretError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"AI mapping chat is not available on this server: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Claude Code run failed: {exc}") from exc
