"""AI provider configuration router (SRS §8.4, §9).

The UI enters the provider API key here; it is encrypted at rest and NEVER
returned. GET exposes a masked hint + whether a key is set. PUT upserts the
tenant's config; POST /test validates it with a metadata-only probe.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.crypto import SecretError
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.enums import AuditAction
from app.services.ai_config_service import AIConfigService
from app.services.ai_service import AIService
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/ai/config", tags=["ai-config"], dependencies=[Depends(require_roles(*BuilderRoles))]
)


class AIConfigBody(BaseModel):
    provider: str = "anthropic"  # anthropic | selfhosted
    model: str = "claude-opus-4-8"
    api_key: str | None = None  # write-only; omit to keep the existing key
    base_url: str | None = None  # self-hosted endpoint
    enabled: bool = True


def _public(cfg) -> dict:  # noqa: ANN001
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "base_url": cfg.base_url,
        "enabled": cfg.enabled,
        "has_api_key": cfg.has_api_key,
        "api_key_hint": cfg.api_key_hint,
        "source": cfg.source,
    }


@router.get("")
def get_config(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return _public(AIConfigService(db).public(ctx.tenant_id))


@router.put("")
def set_config(
    body: AIConfigBody,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    if body.provider not in ("anthropic", "selfhosted"):
        raise HTTPException(status_code=400, detail="provider must be 'anthropic' or 'selfhosted'")
    try:
        cfg = AIConfigService(db).upsert(
            ctx.tenant_id,
            provider=body.provider,
            model=body.model,
            api_key=body.api_key,
            base_url=body.base_url,
            enabled=body.enabled,
            updated_by=ctx.acting_user_id,
        )
    except SecretError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    AuditService(db).log(
        user_id=ctx.acting_user_id,
        action=AuditAction.AI_CONFIG_UPDATED,
        target_type="ai_config",
        detail={"provider": body.provider, "model": body.model, "key_changed": bool(body.api_key)},
    )
    return _public(cfg)


@router.post("/test")
def test_config(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    return AIService(db).test_connection(ctx)
