"""Auth router — JWT from HRIS SSO (Architecture §4.2)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session

from app.api.deps import platform_db_session
from app.core.config import settings
from app.core.security import (
    Principal,
    decode_for_refresh,
    get_principal,
)
from app.core.tenancy import TenantContext, get_tenant_context
from app.domain.enums import Role
from app.repositories.tenant_provision import get_nav_sections
from app.services.hris_refresh import refresh_or_http_exception

router = APIRouter(prefix="/auth", tags=["auth"])

_ROLE_LABEL = {
    Role.SUPPORT_ADMIN: "Support Admin",
    Role.CLIENT_HR_ADMIN: "HR Admin",
    Role.CLIENT_END_USER: "Viewer",
    Role.SYSTEM: "System",
}


def _display_name(email: str | None, user_id: str) -> str:
    local = (email or user_id or "").split("@", 1)[0]
    parts = [p for p in local.replace(".", " ").replace("_", " ").replace("-", " ").split() if p]
    return " ".join(w.capitalize() for w in parts) or (email or user_id)


@router.post("/token")
def issue_token(form: OAuth2PasswordRequestForm = Depends()) -> dict:  # noqa: ARG001
    """Local password grant removed — authenticate via HRIS SSO JWT."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Use HRIS SSO; local user accounts are not stored in Report Builder.",
    )


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[7:].strip()


@router.post("/refresh")
def refresh_access_token(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer(authorization)
    claims = decode_for_refresh(token)
    return refresh_or_http_exception(
        claims.hris_origin,
        token,
        timeout=settings.hris_refresh_timeout_seconds,
    )


@router.get("/company-logo")
def company_logo(principal: Principal = Depends(get_principal)) -> Response:
    if not principal.logo_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No company logo")

    try:
        resp = httpx.get(principal.logo_url, timeout=10.0, follow_redirects=True, verify=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch company logo from HRIS: {principal.logo_url}",
        ) from exc

    media_type = resp.headers.get("content-type") or "application/octet-stream"
    if not media_type.startswith("image/"):
        body = resp.content
        if body[:8] == b"\x89PNG\r\n\x1a\n":
            media_type = "image/png"
        elif body[:2] == b"\xff\xd8":
            media_type = "image/jpeg"
        elif body[:6] in (b"GIF87a", b"GIF89a"):
            media_type = "image/gif"
        elif body[:4] == b"RIFF" and len(body) >= 12 and body[8:12] == b"WEBP":
            media_type = "image/webp"
        else:
            media_type = "image/png"

    return Response(
        content=resp.content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/me")
def whoami(
    principal: Principal = Depends(get_principal),
    ctx: TenantContext = Depends(get_tenant_context),
    platform_db: Session = Depends(platform_db_session),
) -> dict:
    email = getattr(principal, "email", None)
    tenant_name = principal.company_name or ctx.tenant_id.replace("_", " ").title()
    return {
        "user_id": principal.user_id,
        "email": email,
        "name": _display_name(email, principal.user_id),
        "role": principal.role.value,
        "designation": _ROLE_LABEL.get(principal.role, principal.role.value.replace("_", " ").title()),
        "tenant_id": ctx.tenant_id,
        "tenant_name": tenant_name,
        "logo_url": principal.logo_url,
        "nav_sections": get_nav_sections(platform_db, ctx.tenant_id),
    }
