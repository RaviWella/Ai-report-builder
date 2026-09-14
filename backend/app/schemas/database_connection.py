"""MintHRM — database connection Pydantic schemas.

Ported from mint-analytics app/api/routes/database_connections.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── SSH mixin ────────────────────────────────────────────────────

class _SSHFieldsMixin(BaseModel):
    """Shared SSH tunnel fields. Plaintext on the wire — encrypted at rest."""
    ssh_enabled:      Optional[bool]                       = False
    ssh_host:         Optional[str]                        = None
    ssh_port:         Optional[int]                        = Field(None, ge=1, le=65535)
    ssh_username:     Optional[str]                        = None
    ssh_auth_method:  Optional[Literal["password", "key"]] = None
    ssh_password:     Optional[str]                        = None
    ssh_private_key:  Optional[str]                        = None
    ssh_key_passphrase: Optional[str]                      = None


def _validate_ssh(values: BaseModel) -> BaseModel:
    if not getattr(values, "ssh_enabled", False):
        return values
    missing = [
        f for f in ("ssh_host", "ssh_username", "ssh_auth_method")
        if not getattr(values, f, None)
    ]
    if missing:
        raise ValueError(f"ssh_enabled=True requires: {', '.join(missing)}")
    method = values.ssh_auth_method
    if method == "password" and not getattr(values, "ssh_password", None):
        raise ValueError("ssh_auth_method='password' requires ssh_password")
    if method == "key" and not getattr(values, "ssh_private_key", None):
        raise ValueError("ssh_auth_method='key' requires ssh_private_key")
    return values


# ── CRUD schemas ─────────────────────────────────────────────────

class ConnectionCreate(_SSHFieldsMixin):
    name:          str = Field(..., min_length=1, max_length=255)
    engine:        str = Field(..., pattern="^(postgres|mysql|sqlserver)$")
    host:          str = Field(..., min_length=1)
    port:          int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., min_length=1)
    username:      str = Field(..., min_length=1)
    password:      str = Field(..., min_length=1)
    description:   Optional[str]       = None
    default_schema: Optional[str]      = None
    ssl_mode:      Optional[str]       = None
    category:      Optional[str]       = None
    tags:          Optional[List[str]] = None

    @model_validator(mode="after")
    def _ssh_consistent(self):
        return _validate_ssh(self)


class ConnectionUpdate(_SSHFieldsMixin):
    name:          Optional[str] = None
    engine:        Optional[str] = None
    host:          Optional[str] = None
    port:          Optional[int] = None
    database_name: Optional[str] = None
    username:      Optional[str] = None
    password:      Optional[str] = None
    description:   Optional[str] = None
    default_schema: Optional[str] = None
    ssl_mode:      Optional[str] = None
    category:      Optional[str] = None
    tags:          Optional[List[str]] = None
    is_active:     Optional[bool] = None

    @model_validator(mode="after")
    def _ssh_consistent(self):
        return _validate_ssh(self)


class ConnectionOut(BaseModel):
    id:            int
    name:          str
    engine:        str
    host:          str
    port:          int
    database_name: str
    username:      str
    description:   Optional[str]  = None
    default_schema: Optional[str] = None
    ssl_mode:      Optional[str]  = None
    category:      Optional[str]  = None
    tags:          Optional[list] = []
    is_healthy:    bool           = True
    is_active:     bool           = True
    health_check_error: Optional[str] = None
    # SSH — non-secret fields only
    ssh_enabled:     bool          = False
    ssh_host:        Optional[str] = None
    ssh_port:        Optional[int] = None
    ssh_username:    Optional[str] = None
    ssh_auth_method: Optional[str] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    class Config:
        from_attributes = True


class TestConnectionRequest(_SSHFieldsMixin):
    engine:        str
    host:          str
    port:          int
    database_name: str
    username:      str
    password:      str

    @model_validator(mode="after")
    def _ssh_consistent(self):
        return _validate_ssh(self)


class QueryRequest(BaseModel):
    sql:         str            = Field(..., min_length=1)
    limit:       Optional[int] = Field(None, ge=1, le=100_000)
    schema_name: Optional[str] = Field(
        None, description="Schema to set as search_path for this query"
    )


# ── Data Access Rule schemas ─────────────────────────────────────

class RuleCreate(BaseModel):
    name:                   str = Field(..., min_length=1)
    target_column:          str = Field(..., min_length=1)
    apply_to_tables:        List[str]        = ["*"]
    external_api_url:       str = Field(..., min_length=1)
    external_api_method:    str              = "POST"
    external_api_headers:   Dict[str, str]   = {}
    external_api_body:      Dict[str, Any]   = {}
    response_values_path:   str = Field(..., min_length=1)
    cache_ttl_seconds:      int              = 300
    applies_to_roles:       List[str]        = []
    description:            Optional[str]    = None
    priority:               int              = 0


class RuleUpdate(BaseModel):
    name:                   Optional[str]            = None
    target_column:          Optional[str]            = None
    apply_to_tables:        Optional[List[str]]      = None
    external_api_url:       Optional[str]            = None
    external_api_method:    Optional[str]            = None
    external_api_headers:   Optional[Dict[str, str]] = None
    external_api_body:      Optional[Dict[str, Any]] = None
    response_values_path:   Optional[str]            = None
    cache_ttl_seconds:      Optional[int]            = None
    applies_to_roles:       Optional[List[str]]      = None
    description:            Optional[str]            = None
    priority:               Optional[int]            = None
    is_active:              Optional[bool]           = None
