"""Phase 9 — datamart auth context helpers."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.ai_services.datamart import config as dm_config
from app.services.ai_services.datamart.workspace.auth_context import (
    DatamartAuthContext,
    get_datamart_tenant_id_from_auth,
    get_datamart_user_id,
    reset_datamart_auth,
    set_datamart_auth,
)
from app.services.ai_services.datamart.workspace.tenant_dependency import resolve_datamart_tenant_context


@pytest.mark.asyncio
async def test_resolve_datamart_requires_header_when_configured(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    monkeypatch.setattr(dm_config, "DATAMART_REQUIRE_TENANT_HEADER", True)
    with pytest.raises(HTTPException) as exc:
        await resolve_datamart_tenant_context(x_tenant_id=None, authorization=None)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_resolve_datamart_mock_x_user_id(monkeypatch):
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    monkeypatch.setattr(dm_config, "DATAMART_REQUIRE_TENANT_HEADER", True)
    ctx = await resolve_datamart_tenant_context(
        x_tenant_id="demo_tenant",
        x_user_id="header-user-3",
        authorization=None,
    )
    assert ctx.user_id == "header-user-3"


def test_get_datamart_user_id_from_context():
    auth = DatamartAuthContext(tenant_id="acme", user_id="user-42")
    token = set_datamart_auth(auth)
    try:
        assert get_datamart_user_id() == "user-42"
        assert get_datamart_tenant_id_from_auth() == "acme"
    finally:
        reset_datamart_auth(token)
