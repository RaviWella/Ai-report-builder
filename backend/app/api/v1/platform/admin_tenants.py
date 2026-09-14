"""Tenant nav-section permissions APIs (uses existing JWT session — no separate sign-in)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import platform_db_session
from app.core.security import BuilderRoles, require_roles
from app.db.platform_models import TenantProvisionStatus
from app.repositories.tenant_provision import (
    DEFAULT_NAV_SECTION_FLAGS,
    NAV_SECTION_KEYS,
    get_nav_sections,
    normalize_nav_sections,
    set_nav_sections,
)

router = APIRouter(prefix="/platform", tags=["platform-admin"])
logger = logging.getLogger(__name__)

# Same session as the rest of Report Builder (support_admin / client_hr_admin).
_BuilderAuth = Depends(require_roles(*BuilderRoles))


class NavSectionsBody(BaseModel):
    sections: dict[str, bool] = Field(
        ...,
        description=(
            "Full true/false map for gated sections, e.g. "
            '{"Chat": false, "Documents": true, "Viewer": true, ...}'
        ),
    )


def _tenant_payload(row: TenantProvisionStatus) -> dict:
    return {
        "subdomain": row.subdomain,
        "pg_schema": row.pg_schema,
        "datamart_key": row.datamart_key,
        "status": row.status,
        "provisioned_at": row.provisioned_at.isoformat() if row.provisioned_at else None,
        "provisioned_by": row.provisioned_by,
        "nav_sections": normalize_nav_sections(row.nav_sections),
    }


@router.get("/tenants", dependencies=[_BuilderAuth])
def list_tenants(platform_db: Session = Depends(platform_db_session)) -> dict:
    """List all provisioned domains with their nav-section flags."""
    rows = list(
        platform_db.execute(
            select(TenantProvisionStatus).order_by(TenantProvisionStatus.subdomain)
        ).scalars()
    )
    return {
        "tenants": [_tenant_payload(row) for row in rows],
        "section_keys": list(NAV_SECTION_KEYS),
        "defaults": dict(DEFAULT_NAV_SECTION_FLAGS),
    }


@router.get("/tenants/{subdomain}/nav-sections", dependencies=[_BuilderAuth])
def get_tenant_nav_sections(
    subdomain: str,
    platform_db: Session = Depends(platform_db_session),
) -> dict:
    row = platform_db.get(TenantProvisionStatus, subdomain)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Tenant not provisioned: {subdomain}")
    return {
        "subdomain": subdomain,
        "nav_sections": get_nav_sections(platform_db, subdomain),
        "section_keys": list(NAV_SECTION_KEYS),
        "defaults": dict(DEFAULT_NAV_SECTION_FLAGS),
    }


@router.patch("/tenants/{subdomain}/nav-sections", dependencies=[_BuilderAuth])
def patch_tenant_nav_sections(
    subdomain: str,
    body: NavSectionsBody,
    platform_db: Session = Depends(platform_db_session),
) -> dict:
    try:
        row = set_nav_sections(platform_db, subdomain, body.sections)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    effective = normalize_nav_sections(row.nav_sections)
    platform_db.commit()
    logger.info(
        "Support admin updated nav_sections",
        extra={"subdomain": subdomain, "sections": effective},
    )
    return {
        "subdomain": subdomain,
        "nav_sections": effective,
        "section_keys": list(NAV_SECTION_KEYS),
        "defaults": dict(DEFAULT_NAV_SECTION_FLAGS),
    }
