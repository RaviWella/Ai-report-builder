"""Helpers for platform.tenant_provision_status."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.platform_models import TenantProvisionStatus
from app.tenancy.subdomain import normalize_subdomain

_ACTIVE = "active"

_TEMPLATES = "Templates"

# Gated tenant sidebar sections (Templates always visible; Config / AI Settings
# are admin-only under Observations and are not grantable here).
NAV_SECTION_KEYS: tuple[str, ...] = (
    "Chat",
    "Builder",
    "Documents",
    "Viewer",
    "How it works",
)

KNOWN_NAV_SECTIONS: frozenset[str] = frozenset({_TEMPLATES, *NAV_SECTION_KEYS})
# Formerly grantable; now admin-only under Observations — ignored if still present in JSON.
ADMIN_ONLY_NAV_SECTIONS: frozenset[str] = frozenset({"Config", "AI Settings"})

# Default for every domain: Documents + Viewer on; other gated sections off.
DEFAULT_NAV_SECTION_FLAGS: dict[str, bool] = {
    "Chat": False,
    "Builder": False,
    "Documents": True,
    "Viewer": True,
    "How it works": False,
}

# Backward-compat aliases used by older call sites / tests.
DEFAULT_NAV_SECTIONS: list[str] = [_TEMPLATES, "Documents", "Viewer"]
DEFAULT_STORED_NAV_SECTIONS: dict[str, bool] = dict(DEFAULT_NAV_SECTION_FLAGS)


def default_datamart_key(subdomain: str) -> str:
    """Warehouse DB suffix for a HRIS host label (coca-cola → coca_cola)."""
    return normalize_subdomain(subdomain)


def is_tenant_provisioned(session: Session, subdomain: str) -> bool:
    row = get_provision_status(session, subdomain)
    return row is not None and row.status == _ACTIVE


def get_provision_status(session: Session, subdomain: str) -> TenantProvisionStatus | None:
    row = session.get(TenantProvisionStatus, subdomain)
    if row is not None:
        return row
    normalized = normalize_subdomain(subdomain)
    if normalized != subdomain:
        return session.get(TenantProvisionStatus, normalized)
    return None


def get_datamart_key(session: Session, subdomain: str) -> str:
    row = get_provision_status(session, subdomain)
    if row is not None and row.datamart_key:
        return default_datamart_key(row.datamart_key)
    return default_datamart_key(subdomain)


def ensure_tenant_provision_record(
    session: Session,
    subdomain: str,
    pg_schema: str,
    *,
    datamart_key: str | None = None,
    provisioned_by: str | None = "lazy_provision",
) -> bool:
    if is_tenant_provisioned(session, subdomain):
        return False
    mark_tenant_provisioned(
        session,
        subdomain,
        pg_schema,
        datamart_key=default_datamart_key(datamart_key or subdomain),
        provisioned_by=provisioned_by,
    )
    return True


def mark_tenant_provisioned(
    session: Session,
    subdomain: str,
    pg_schema: str,
    *,
    datamart_key: str | None = None,
    provisioned_by: str | None = None,
) -> TenantProvisionStatus:
    row = session.get(TenantProvisionStatus, subdomain)
    if row is None:
        row = TenantProvisionStatus(
            subdomain=subdomain,
            pg_schema=pg_schema,
            datamart_key=default_datamart_key(datamart_key or subdomain),
            status=_ACTIVE,
            provisioned_by=provisioned_by,
            nav_sections=dict(DEFAULT_NAV_SECTION_FLAGS),
        )
        session.add(row)
    else:
        row.pg_schema = pg_schema
        row.datamart_key = default_datamart_key(
            datamart_key or row.datamart_key or subdomain
        )
        row.status = _ACTIVE
        if provisioned_by is not None:
            row.provisioned_by = provisioned_by
    session.flush()
    return row


def list_active_tenants(session: Session) -> list[TenantProvisionStatus]:
    from sqlalchemy import select

    return list(
        session.execute(
            select(TenantProvisionStatus).where(TenantProvisionStatus.status == _ACTIVE)
        ).scalars()
    )


def _flags_from_allow_list(names: list[Any]) -> dict[str, bool]:
    enabled = {
        item.strip()
        for item in names
        if isinstance(item, str) and item.strip() in KNOWN_NAV_SECTIONS
    }
    return {key: key in enabled for key in NAV_SECTION_KEYS}


def normalize_nav_sections(raw: Any) -> dict[str, bool]:
    """Parse stored JSON into a full true/false map for every gated section.

    Supports:
      - new shape: {"Chat": false, "Documents": true, ...}
      - legacy shape: {"sections": ["Documents", "Viewer"]}
    Null / unrecognized input falls back to DEFAULT_NAV_SECTION_FLAGS.
    Templates is never stored (always visible in the UI).
    """
    if raw is None:
        return dict(DEFAULT_NAV_SECTION_FLAGS)

    if isinstance(raw, list):
        return _flags_from_allow_list(raw)

    if not isinstance(raw, dict):
        return dict(DEFAULT_NAV_SECTION_FLAGS)

    # Legacy allow-list wrapper.
    if "sections" in raw and isinstance(raw.get("sections"), list):
        return _flags_from_allow_list(raw["sections"])

    # New boolean map (may be partial — fill missing keys from defaults).
    has_any_known_flag = any(key in raw for key in NAV_SECTION_KEYS)
    if not has_any_known_flag:
        return dict(DEFAULT_NAV_SECTION_FLAGS)

    flags = dict(DEFAULT_NAV_SECTION_FLAGS)
    for key in NAV_SECTION_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool):
            flags[key] = value
        elif isinstance(value, (int, float)) and value in (0, 1):
            flags[key] = bool(value)
        elif isinstance(value, str) and value.strip().lower() in ("true", "false"):
            flags[key] = value.strip().lower() == "true"
    return flags


def enabled_nav_sections(flags: dict[str, bool]) -> list[str]:
    """Effective visible labels: Templates + every gated section set to true."""
    return [_TEMPLATES, *[key for key in NAV_SECTION_KEYS if flags.get(key)]]


def get_nav_sections(session: Session, subdomain: str) -> dict[str, bool]:
    row = get_provision_status(session, subdomain)
    if row is None:
        return dict(DEFAULT_NAV_SECTION_FLAGS)
    return normalize_nav_sections(row.nav_sections)


def set_nav_sections(
    session: Session,
    subdomain: str,
    sections: dict[str, bool] | list[str],
) -> TenantProvisionStatus:
    """Persist full true/false map for all gated sections.

    Accepts the new boolean map, or a legacy allow-list of enabled names.
    """
    row = get_provision_status(session, subdomain)
    if row is None:
        raise LookupError(f"Tenant not provisioned: {subdomain}")

    if isinstance(sections, list):
        unknown = sorted(
            {
                s.strip()
                for s in sections
                if s.strip()
                and s.strip() not in KNOWN_NAV_SECTIONS
                and s.strip() not in ADMIN_ONLY_NAV_SECTIONS
            }
        )
        if unknown:
            raise ValueError(f"Unknown nav sections: {', '.join(unknown)}")
        flags = _flags_from_allow_list(sections)
    elif isinstance(sections, dict):
        unknown = sorted(
            {
                str(key)
                for key in sections
                if key not in NAV_SECTION_KEYS
                and key != _TEMPLATES
                and key not in ADMIN_ONLY_NAV_SECTIONS
            }
        )
        if unknown:
            raise ValueError(f"Unknown nav sections: {', '.join(unknown)}")
        flags = normalize_nav_sections(sections)
    else:
        raise ValueError("nav_sections must be an object of boolean flags")

    row.nav_sections = flags
    session.flush()
    return row
