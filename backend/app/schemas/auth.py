"""MintHRM — tenant/user context schema.

Mirrors mint-analytics app/schemas/auth.py (UserContext) but adapted for
the HRM multi-tenant model where the identity key is tenant_id rather than
org_id.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class TenantContext(BaseModel):
    """Authenticated request context for multi-tenant HRM operations.

    In mock-auth mode the context is built directly from the X-Tenant-Id
    header.  In real-auth mode it will be extracted from a validated JWT.

    Schema names resolve from tenant_registry (dedicated warehouse DB or legacy prefix).
    """

    tenant_id: str

    # Optional fields populated from JWT in real-auth mode
    user_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None

    # Permissions (for future use with real auth)
    permissions: List[str] = []
    role: str = "user"

    # ── Derived schema names ─────────────────────────────────────────

    def _layout(self):
        from app.core.warehouse import get_layout_sync

        return get_layout_sync(self.tenant_id)

    @property
    def mart_schema(self) -> str:
        return self._layout().mart_schema

    @property
    def raw_schema(self) -> str:
        return self._layout().raw_schema

    @property
    def semantic_schema(self) -> str:
        return self._layout().semantic_schema

    @property
    def control_schema(self) -> str:
        return self._layout().control_schema
