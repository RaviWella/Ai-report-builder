"""Tenant resolution & scope (Architecture §4.2, §7.1)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.core.security import Principal, get_principal
from app.domain.enums import Role
from app.tenancy.pg_schema import subdomain_to_pg_schema


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    pg_schema: str
    acting_user_id: str
    role: Role
    on_behalf: bool


def get_tenant_context(
    principal: Principal = Depends(get_principal),
    x_act_as_tenant: str | None = Header(default=None, alias="X-Act-As-Tenant"),
) -> TenantContext:
    tenant_id = principal.tenant_id
    on_behalf = False

    if x_act_as_tenant and x_act_as_tenant != principal.tenant_id:
        if principal.role != Role.SUPPORT_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only MintHRM support may act on behalf of another tenant",
            )
        tenant_id = x_act_as_tenant
        on_behalf = True

    return TenantContext(
        tenant_id=tenant_id,
        pg_schema=subdomain_to_pg_schema(tenant_id),
        acting_user_id=principal.user_id,
        role=principal.role,
        on_behalf=on_behalf,
    )
