"""Datamart request auth context (Phase 9 — platform JWT / mock headers)."""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional

from .. import config as dm_config

_auth_ctx: ContextVar[Optional["DatamartAuthContext"]] = ContextVar(
    "datamart_auth",
    default=None,
)


@dataclass(frozen=True)
class DatamartAuthContext:
    tenant_id: str
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: str = "user"


def set_datamart_auth(ctx: DatamartAuthContext) -> Token:
    return _auth_ctx.set(ctx)


def reset_datamart_auth(token: Token) -> None:
    try:
        _auth_ctx.reset(token)
    except ValueError:
        _auth_ctx.set(None)


def get_datamart_auth() -> Optional[DatamartAuthContext]:
    return _auth_ctx.get()


def get_datamart_user_id() -> str:
    """User id for workspace rows (from request context or default)."""
    auth = get_datamart_auth()
    if auth is not None:
        return auth.user_id
    return dm_config.DATAMART_DEFAULT_USER_ID


def get_datamart_tenant_id_from_auth() -> str:
    """Tenant id from request auth context (for agent thread pool)."""
    auth = get_datamart_auth()
    if auth is not None:
        return auth.tenant_id
    return dm_config.DATAMART_DEFAULT_TENANT_ID
