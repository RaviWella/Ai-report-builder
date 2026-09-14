"""MintHRM — API key + tenant auth (mock headers or JWT)."""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt

from app.core.config import settings
from app.schemas.auth import TenantContext

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _coerce_header(value: object) -> str:
    """Normalize FastAPI Header() defaults and direct calls (not only DI)."""
    if isinstance(value, str):
        return value.strip()
    return ""


def mock_auth_enabled() -> bool:
    """When true, X-Tenant-Id mock path is allowed; JWT still works if Bearer sent."""
    raw = os.getenv("MOCK_AUTH_ENABLED", "true" if settings.DEBUG else "false")
    return raw.strip().lower() in ("1", "true", "yes")


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "API-Key"},
        )
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return api_key


def validate_tenant_id(tenant_id: str) -> bool:
    """Only alphanumeric + underscores — prevents schema-name injection."""
    return bool(re.match(r"^[a-zA-Z0-9_]+$", tenant_id))


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not str(authorization).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw = str(authorization).strip()
    prefix = "Bearer "
    if not raw.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must use Bearer scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = raw[len(prefix) :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is empty",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate HS256 JWT signed with SECRET_KEY / ALGORITHM."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired access token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _claim_str(payload: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def tenant_context_from_jwt_payload(payload: dict[str, Any]) -> TenantContext:
    tenant_id = _claim_str(payload, "tenant_id", "tid", "org_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing tenant_id (or tid / org_id claim)",
        )
    if not validate_tenant_id(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid tenant ID in token. "
                "Only alphanumeric characters and underscores allowed."
            ),
        )

    user_id = _claim_str(payload, "user_id", "uid", "sub")
    email = _claim_str(payload, "email")
    name = _claim_str(payload, "name", "full_name")
    role = _claim_str(payload, "role") or "user"

    permissions: list[str] = []
    raw_perm = payload.get("permissions") or payload.get("scopes") or payload.get("scope")
    if isinstance(raw_perm, list):
        permissions = [str(p) for p in raw_perm if p]
    elif isinstance(raw_perm, str) and raw_perm.strip():
        permissions = [p.strip() for p in raw_perm.replace(",", " ").split() if p.strip()]

    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        name=name,
        permissions=permissions,
        role=role,
    )


def create_access_token(
    *,
    tenant_id: str,
    user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    role: str = "user",
    permissions: Optional[list[str]] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """Issue a dev/test JWT (same secret as decode_access_token)."""
    from datetime import datetime, timedelta, timezone

    expire = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": email or f"{user_id}@local.dev",
        "name": name or user_id,
        "role": role,
        "permissions": permissions or ["read", "write"],
        "iat": now,
        "exp": now + timedelta(minutes=expire),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None),
) -> TenantContext:
    """
    Authenticated tenant context for HR and datamart routes.

    - Bearer JWT: validated with SECRET_KEY (production path when MOCK_AUTH_ENABLED=false).
    - Mock mode: X-Tenant-Id required unless Bearer token is sent (JWT still validated).
    """
    auth_hdr = _coerce_header(authorization)
    tenant_hdr = _coerce_header(x_tenant_id)
    user_hdr = _coerce_header(x_user_id)

    if auth_hdr:
        ctx = tenant_context_from_jwt_payload(decode_access_token(_extract_bearer_token(auth_hdr)))
        if tenant_hdr and tenant_hdr != ctx.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="X-Tenant-Id does not match token tenant_id",
            )
        return ctx

    if not mock_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not tenant_hdr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required",
        )
    if not validate_tenant_id(tenant_hdr):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid tenant ID format. "
                "Only alphanumeric characters and underscores allowed."
            ),
        )
    if not user_hdr:
        from app.services.ai_services.datamart.config import DATAMART_DEFAULT_USER_ID

        user_hdr = DATAMART_DEFAULT_USER_ID
    return TenantContext(
        tenant_id=tenant_hdr,
        user_id=user_hdr,
        email="testuser@example.com",
        name="Test User",
        permissions=["read", "write", "admin"],
        role="admin",
    )
