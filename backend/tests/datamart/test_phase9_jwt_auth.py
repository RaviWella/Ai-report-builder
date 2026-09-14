"""Phase 9 — JWT auth and datamart platform auth wiring."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_current_tenant,
    mock_auth_enabled,
    tenant_context_from_jwt_payload,
)
from app.services.ai_services.datamart import config as dm_config
from app.services.ai_services.datamart.workspace.auth_context import DatamartAuthContext
from app.services.ai_services.datamart.workspace.tenant_dependency import (
    _auth_from_tenant_context,
    resolve_datamart_tenant_context,
)


def test_create_and_decode_jwt_roundtrip():
    token = create_access_token(
        tenant_id="demo_tenant",
        user_id="user-99",
        email="a@example.com",
        role="admin",
    )
    payload = decode_access_token(token)
    ctx = tenant_context_from_jwt_payload(payload)
    assert ctx.tenant_id == "demo_tenant"
    assert ctx.user_id == "user-99"
    assert ctx.email == "a@example.com"
    assert ctx.role == "admin"


@pytest.mark.asyncio
async def test_get_current_tenant_jwt_path(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "false")
    token = create_access_token(tenant_id="acme_corp", user_id="jwt-user")
    ctx = await get_current_tenant(
        x_tenant_id="acme_corp",
        authorization=f"Bearer {token}",
    )
    assert ctx.tenant_id == "acme_corp"
    assert ctx.user_id == "jwt-user"


@pytest.mark.asyncio
async def test_get_current_tenant_jwt_mismatch_tenant_header(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "false")
    token = create_access_token(tenant_id="acme_corp", user_id="jwt-user")
    with pytest.raises(HTTPException) as exc:
        await get_current_tenant(
            x_tenant_id="other_tenant",
            authorization=f"Bearer {token}",
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_tenant_mock_requires_header(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    assert mock_auth_enabled() is True
    with pytest.raises(HTTPException) as exc:
        await get_current_tenant(x_tenant_id=None, authorization=None)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_current_tenant_mock_respects_x_user_id(monkeypatch):
    """Regression: direct call must not treat Header() default as a string."""
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    ctx = await get_current_tenant(
        x_tenant_id="demo_tenant",
        x_user_id="default-user",
        authorization=None,
    )
    assert ctx.tenant_id == "demo_tenant"
    assert ctx.user_id == "default-user"


@pytest.mark.asyncio
async def test_resolve_datamart_with_tenant_and_user_headers(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    monkeypatch.setattr(dm_config, "DATAMART_REQUIRE_TENANT_HEADER", True)
    ctx = await resolve_datamart_tenant_context(
        x_tenant_id="demo_tenant",
        x_user_id="default-user",
        authorization=None,
    )
    assert ctx.tenant_id == "demo_tenant"
    assert ctx.user_id == "default-user"


@pytest.mark.asyncio
async def test_resolve_datamart_default_tenant_dev(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    monkeypatch.setattr(dm_config, "DATAMART_REQUIRE_TENANT_HEADER", False)
    ctx = await resolve_datamart_tenant_context(x_tenant_id=None, authorization=None)
    assert ctx.tenant_id == "demo_tenant"
    assert ctx.user_id == dm_config.DATAMART_DEFAULT_USER_ID


@pytest.mark.asyncio
async def test_resolve_datamart_jwt_user_id(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "false")
    monkeypatch.setattr(dm_config, "DATAMART_REQUIRE_TENANT_HEADER", True)
    token = create_access_token(tenant_id="demo_tenant", user_id="real-user-7")
    ctx = await resolve_datamart_tenant_context(
        x_tenant_id="demo_tenant",
        authorization=f"Bearer {token}",
    )
    auth = _auth_from_tenant_context(ctx)
    assert auth.user_id == "real-user-7"
    assert isinstance(auth, DatamartAuthContext)


def test_expired_token_rejected():
    token = jwt.encode(
        {"tenant_id": "demo_tenant", "user_id": "x", "exp": 0},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401
