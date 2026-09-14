"""Validate decrypted HRIS launch claims and tenant registry."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text

from app.core.config import settings
from app.core.security import validate_tenant_id
from app.core.warehouse import get_platform_engine_sync
from app.services.hris_launch.crypto import (
    HrisPayloadDecryptError,
    decrypt_hris_payload_with_configured_secrets,
)


@dataclass(frozen=True)
class HrisLaunchClaims:
    tenant_id: str
    user_id: str
    email: Optional[str]
    name: Optional[str]
    permissions: list[str]
    company_name: Optional[str]
    logo_url: Optional[str]


class HrisLaunchValidationError(ValueError):
    """Launch payload failed business validation."""


def _str_field(data: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _permissions_list(data: dict[str, Any]) -> list[str]:
    raw = data.get("permissions") or data.get("scopes") or data.get("scope")
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if p and str(p).strip()]
    if isinstance(raw, str) and raw.strip():
        return [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    return []


def _has_warehouse_permission_from_data(data: dict[str, Any], permissions: list[str]) -> bool:
    required = (settings.HRIS_WAREHOUSE_PERMISSION or "warehouse_access").strip().lower()
    lowered = {p.lower() for p in permissions}
    if required in lowered:
        return True
    for p in lowered:
        if "warehouse" in p or p in ("analytics", "analytics_access"):
            return True
    if data.get("warehouse_access") is True:
        return True
    if str(data.get("can_access_warehouse", "")).lower() in ("1", "true", "yes"):
        return True
    return False


def _tenant_active(tenant_id: str) -> tuple[bool, Optional[str]]:
    """Return (exists_and_active, display_name)."""
    eng = get_platform_engine_sync()
    with eng.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT tenant_id, display_name, is_active
                FROM hrm_control.tenant_registry
                WHERE tenant_id = :tid
                LIMIT 1
                """
            ),
            {"tid": tenant_id},
        ).mappings().first()
    if not row:
        return False, None
    if not bool(row.get("is_active", True)):
        return False, str(row.get("display_name") or "") or None
    return True, str(row.get("display_name") or "") or None


def parse_and_validate_launch_payload(
    payload_b64: str,
    *,
    query_subdomain: Optional[str] = None,
    query_employee_id: Optional[str] = None,
) -> HrisLaunchClaims:
    try:
        data = decrypt_hris_payload_with_configured_secrets(payload_b64)
    except HrisPayloadDecryptError as exc:
        raise HrisLaunchValidationError(str(exc)) from exc

    tenant_id = _str_field(data, "tenant_id", "subdomain", "tid")
    if not tenant_id:
        raise HrisLaunchValidationError("Launch payload missing tenant_id or subdomain")

    if not validate_tenant_id(tenant_id):
        raise HrisLaunchValidationError("Invalid tenant_id format")

    user_id = _str_field(
        data,
        "user_id",
        "employee_id",
        "user_emp_id",
        "emp_id",
        "uid",
        "sub",
    )
    if not user_id:
        raise HrisLaunchValidationError(
            "Launch payload missing user_emp_id, employee_id, or user_id"
        )

    if query_subdomain and query_subdomain.strip().lower() != tenant_id.strip().lower():
        raise HrisLaunchValidationError("subdomain does not match payload tenant")

    if query_employee_id and query_employee_id.strip() != user_id:
        raise HrisLaunchValidationError("employee_id does not match payload user")

    exp = data.get("exp")
    if exp is not None:
        try:
            exp_ts = int(exp)
        except (TypeError, ValueError) as exc:
            raise HrisLaunchValidationError("Invalid exp in launch payload") from exc
        skew = max(0, int(settings.HRIS_LAUNCH_CLOCK_SKEW_SEC))
        if time.time() > exp_ts + skew:
            raise HrisLaunchValidationError("Launch payload has expired")

    permissions = _permissions_list(data)
    # MinHRM actionLaunchAnalytics checks Permission::systemModulePermission(11012)
    # before encrypting; one-time auth token is in payload, not a permissions list.
    php_launch_token = _str_field(data, "token", "auth_code", "auth_token")
    if not php_launch_token and not _has_warehouse_permission_from_data(data, permissions):
        raise HrisLaunchValidationError("User does not have warehouse access")

    active, registry_name = _tenant_active(tenant_id)
    if not active and settings.HRIS_LAUNCH_AUTO_PROVISION_TENANT:
        from app.services.tenant_provision import provision_tenant_minimal_sync

        provision_tenant_minimal_sync(
            tenant_id,
            display_name=_str_field(data, "company_name", "company") or tenant_id,
        )
        active, registry_name = _tenant_active(tenant_id)

    if not active:
        raise HrisLaunchValidationError(f"Unknown or inactive tenant: {tenant_id}")

    company_name = _str_field(data, "company_name", "company") or registry_name
    logo_url = _str_field(data, "logo_url", "logo", "company_logo", "company_logo_url")

    return HrisLaunchClaims(
        tenant_id=tenant_id,
        user_id=user_id,
        email=_str_field(data, "email"),
        name=_str_field(data, "name", "full_name", "employee_name"),
        permissions=permissions or [settings.HRIS_WAREHOUSE_PERMISSION or "warehouse_access"],
        company_name=company_name,
        logo_url=logo_url,
    )
