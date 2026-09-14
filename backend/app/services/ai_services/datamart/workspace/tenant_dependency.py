"""FastAPI dependency: datamart warehouse + platform auth (Phase 9)."""
from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, Header

from app.core.security import get_current_tenant, mock_auth_enabled
from app.schemas.auth import TenantContext

from .. import config as dm_config
from .auth_context import (
    DatamartAuthContext,
    reset_datamart_auth,
    set_datamart_auth,
)
from .runtime_context import (
    reset_datamart_context,
    resolve_datamart_context,
    set_datamart_context,
)


def _header_value(value: object) -> str:
    """Normalize FastAPI-injected headers (tests may omit optional args)."""
    if isinstance(value, str):
        return value.strip()
    return ""


def resolve_datamart_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None),
) -> TenantContext:
    """
    Datamart auth aligned with HR routes.

    - Production (MOCK_AUTH_ENABLED=false): Bearer JWT required; tenant from token.
    - Dev with DATAMART_REQUIRE_TENANT_HEADER=false: allow default tenant when no headers.
    - Dev otherwise: same as get_current_tenant (X-Tenant-Id and/or Bearer).
    """
    tenant_hdr = _header_value(x_tenant_id)
    user_hdr = _header_value(x_user_id)
    auth_hdr = _header_value(authorization)
    has_tenant_header = bool(tenant_hdr)
    has_bearer = bool(auth_hdr)

    # No tenant on the request → default warehouse tenant (demo_tenant in dev).
    if not has_tenant_header and not has_bearer:
        if not dm_config.DATAMART_REQUIRE_TENANT_HEADER and mock_auth_enabled():
            uid = user_hdr or dm_config.DATAMART_DEFAULT_USER_ID
            return TenantContext(
                tenant_id=dm_config.DATAMART_DEFAULT_TENANT_ID,
                user_id=uid,
                email="dev@local",
                name="Dev User",
                permissions=["read", "write", "admin"],
                role="admin",
            )
        if not mock_auth_enabled():
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required",
        )

    ctx = get_current_tenant(
        x_tenant_id=tenant_hdr or None,
        x_user_id=user_hdr or None,
        authorization=auth_hdr or None,
    )
    return ctx


def _auth_from_tenant_context(tenant_ctx: TenantContext) -> DatamartAuthContext:
    user_id = (tenant_ctx.user_id or "").strip() or dm_config.DATAMART_DEFAULT_USER_ID
    return DatamartAuthContext(
        tenant_id=tenant_ctx.tenant_id,
        user_id=user_id,
        email=tenant_ctx.email,
        name=tenant_ctx.name,
        role=tenant_ctx.role,
    )


def get_datamart_auth(
    tenant_ctx: TenantContext = Depends(resolve_datamart_tenant_context),
) -> DatamartAuthContext:
    """Resolved tenant + user for workspace DB rows."""
    return _auth_from_tenant_context(tenant_ctx)


def datamart_runtime_dependency(
    auth: DatamartAuthContext = Depends(get_datamart_auth),
) -> Generator[DatamartAuthContext, None, None]:
    """
    Set warehouse + auth contextvars for sync handlers on this request.

    Must be a sync generator (not async): async deps run in the event-loop context
    while sync route handlers run in a worker thread, so contextvar reset raises
    ``ValueError: Token was created in a different Context``.
    """
    ctx = resolve_datamart_context(auth.tenant_id)
    ctx_token = set_datamart_context(ctx)
    auth_token = set_datamart_auth(auth)
    try:
        yield auth
    finally:
        reset_datamart_context(ctx_token)
        reset_datamart_auth(auth_token)
