"""Internal tenant onboarding — PG provision status and schema creation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.pg_tenant_session import get_postgres_tenant_session_manager
from app.db.postgres import get_postgres_database
from app.services.tenant_scope import clear_datamart_key_cache
from app.repositories.tenant_provision import (
    DEFAULT_NAV_SECTION_FLAGS,
    NAV_SECTION_KEYS,
    get_nav_sections,
    mark_tenant_provisioned,
    normalize_nav_sections,
    set_nav_sections,
)
from app.tenancy.pg_schema import subdomain_to_pg_schema
from sqlalchemy import text

router = APIRouter(prefix="/platform", tags=["platform"])
logger = logging.getLogger(__name__)


class ProvisionRequest(BaseModel):
    datamart_key: str | None = Field(
        default=None,
        description="Warehouse DB key (defaults to hyphen-folded subdomain, e.g. coca-cola → coca_cola)",
    )
    nav_sections: dict[str, bool] | None = Field(
        default=None,
        description=(
            "Optional sidebar flags for all gated sections, e.g. "
            '{"Chat": false, "Documents": true, "Viewer": true, ...}'
        ),
    )


class NavSectionsRequest(BaseModel):
    sections: dict[str, bool] = Field(
        ...,
        description=(
            "Full true/false map for gated sections, e.g. "
            '{"Chat": false, "Builder": false, "Documents": true, "Viewer": true, '
            '"Config": false, "AI Settings": false, "How it works": false}'
        ),
    )


def _check_internal_provision_key(
    x_internal_provision_key: str | None = Header(default=None, alias="X-Internal-Provision-Key"),
) -> None:
    expected = settings.pg_provision_api_key
    if not expected:
        return
    if x_internal_provision_key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Internal-Provision-Key")


@router.post("/internal/tenants/{subdomain}/provision")
def provision_tenant_pg_schema(
    subdomain: str,
    body: ProvisionRequest | None = None,
    _auth: None = Depends(_check_internal_provision_key),
) -> dict:
    """Record PG onboarding and ensure the tenant PostgreSQL schema exists (idempotent)."""
    schema_name = subdomain_to_pg_schema(subdomain)
    datamart_key = body.datamart_key if body else None

    pg_session = get_postgres_database().session()
    try:
        pg_session.execute(text("SET search_path TO platform, public"))
        row = mark_tenant_provisioned(
            pg_session,
            subdomain,
            schema_name,
            datamart_key=datamart_key,
            provisioned_by="internal_api",
        )
        if body and body.nav_sections is not None:
            try:
                set_nav_sections(pg_session, subdomain, body.nav_sections)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        effective_nav = get_nav_sections(pg_session, subdomain)
        pg_session.commit()
        datamart_key = row.datamart_key
        clear_datamart_key_cache(subdomain)
        logger.info("Marked tenant provisioned in PG", extra={"subdomain": subdomain})
    finally:
        pg_session.close()

    created = get_postgres_tenant_session_manager().ensure_tenant_schema(subdomain)

    return {
        "schema": schema_name,
        "datamart_key": datamart_key,
        "provisioned": True,
        "schema_created": created,
        "nav_sections": effective_nav,
    }


@router.patch("/internal/tenants/{subdomain}/nav-sections")
def update_tenant_nav_sections(
    subdomain: str,
    body: NavSectionsRequest,
    _auth: None = Depends(_check_internal_provision_key),
) -> dict:
    """Set Report Builder sidebar section flags for a provisioned tenant."""
    pg_session = get_postgres_database().session()
    try:
        pg_session.execute(text("SET search_path TO platform, public"))
        try:
            row = set_nav_sections(pg_session, subdomain, body.sections)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stored = dict(row.nav_sections or {})
        effective = normalize_nav_sections(row.nav_sections)
        pg_session.commit()
        logger.info(
            "Updated tenant nav_sections",
            extra={"subdomain": subdomain, "sections": effective},
        )
    finally:
        pg_session.close()

    return {
        "subdomain": subdomain,
        "stored": stored,
        "nav_sections": effective,
        "known_sections": list(NAV_SECTION_KEYS),
        "defaults": dict(DEFAULT_NAV_SECTION_FLAGS),
    }
