"""Resolve per-tenant vs legacy semantic catalog paths (Phase 11)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..workspace.runtime_context import get_datamart_context

logger = logging.getLogger("ai_services.datamart.semantic")

_PACKAGE_DIR = Path(__file__).resolve().parent
LEGACY_CATALOG_PATH = _PACKAGE_DIR / "semantic_catalog.yaml"
TENANT_CATALOG_DIR = _PACKAGE_DIR / "semantic_catalogs"


def tenant_catalog_path(tenant_id: str) -> Path:
    tid = (tenant_id or "").strip()
    if not tid:
        raise ValueError("tenant_id required for tenant semantic catalog path")
    return TENANT_CATALOG_DIR / f"{tid}.yaml"


def resolve_semantic_catalog_path(
    *,
    tenant_id: Optional[str] = None,
) -> Path:
    """
    Legacy audit: packaged ``semantic_catalog.yaml``.

    Tenant ETL: ``semantic_catalogs/{tenant_id}.yaml`` only (run semantic_catalog_tool --tenant).

    Legacy audit (deprecated): packaged ``semantic_catalog.yaml``.
    """
    ctx = get_datamart_context()
    if ctx is not None and ctx.is_tenant_etl:
        tid = (tenant_id or ctx.tenant_id).strip()
        path = tenant_catalog_path(tid)
        if not path.is_file():
            logger.warning(
                "Tenant semantic catalog missing: %s — run "
                "python tools/semantic_catalog_tool.py refresh --tenant %s --write",
                path,
                tid,
            )
        return path
    if LEGACY_CATALOG_PATH.is_file():
        return LEGACY_CATALOG_PATH
    tid = (tenant_id or (ctx.tenant_id if ctx else "") or "").strip()
    if tid:
        return tenant_catalog_path(tid)
    return LEGACY_CATALOG_PATH


def catalog_path_for_tenant_cli(tenant_id: str) -> Path:
    """Target path for semantic_catalog_tool --tenant (always tenant file)."""
    return tenant_catalog_path(tenant_id.strip())
