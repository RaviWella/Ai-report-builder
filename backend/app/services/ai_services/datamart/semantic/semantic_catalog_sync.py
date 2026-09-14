"""Refresh tenant semantic catalog YAML from live warehouse (Sync button / bootstrap)."""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from .semantic_catalog_paths import catalog_path_for_tenant_cli

logger = logging.getLogger("ai_services.datamart.catalog_sync")

_CATALOG_TOOL_MOD: Optional[Any] = None


def _catalog_tool():
    """Load tools/semantic_catalog_tool.py without making tools/ a package."""
    global _CATALOG_TOOL_MOD
    if _CATALOG_TOOL_MOD is not None:
        return _CATALOG_TOOL_MOD
    backend_root = Path(__file__).resolve().parents[4]
    tool_path = backend_root / "tools" / "semantic_catalog_tool.py"
    mod_name = "app._semantic_catalog_tool_impl"
    spec = importlib.util.spec_from_file_location(mod_name, tool_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load semantic catalog tool from {tool_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _CATALOG_TOOL_MOD = mod
    return mod


def _refresh_report_to_dict(report: Any, catalog_path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    if getattr(report, "missing_tables", None):
        warnings.append(
            "Catalog still references missing tables: "
            + ", ".join(report.missing_tables[:12])
        )
    if getattr(report, "unknown_columns", None):
        for tbl, cols in list(report.unknown_columns.items())[:5]:
            warnings.append(f"Unknown columns on {tbl}: {', '.join(cols[:6])}")

    return {
        "ok": not (report.missing_tables or report.unknown_columns),
        "catalog_path": str(catalog_path),
        "topics_tables_added": dict(getattr(report, "topics_tables_added", {}) or {}),
        "topics_tables_removed": dict(getattr(report, "topics_tables_removed", {}) or {}),
        "joins_added": len(getattr(report, "joins_added", []) or []),
        "dimension_stubs_added": list(getattr(report, "dimension_stubs_added", []) or []),
        "removed_dimensions": list(getattr(report, "removed_dimensions", []) or []),
        "warehouse_only_tables": list(getattr(report, "warehouse_only_tables", []) or [])[:20],
        "warnings": warnings,
    }


def refresh_semantic_catalog_for_tenant(
    tenant_id: str,
    *,
    add_dimension_stubs: bool = True,
) -> dict[str, Any]:
    """
    Merge live warehouse schema into ``semantic_catalogs/{tenant_id}.yaml``.

    Same logic as ``python tools/semantic_catalog_tool.py refresh --tenant … --write``.
    """
    tid = (tenant_id or "").strip()
    if not tid:
        raise ValueError("tenant_id is required for catalog refresh")

    tool = _catalog_tool()
    catalog_path = catalog_path_for_tenant_cli(tid)
    snap = tool._snapshot_warehouse(tid)
    if not snap.tables:
        raise ValueError(
            f"No tables found in warehouse schemas ({snap.schema}) for tenant {tid}."
        )

    catalog = tool._load_catalog_for_command(catalog_path, tid)
    report = tool.refresh_catalog(
        catalog,
        snap,
        add_dimension_stubs=add_dimension_stubs,
    )
    tool._save_catalog(catalog_path, catalog, tenant_id=tid)
    logger.info(
        "semantic catalog refreshed tenant=%s path=%s tables=%d joins_added=%d",
        tid,
        catalog_path.name,
        len(snap.tables),
        len(report.joins_added),
    )
    out = _refresh_report_to_dict(report, catalog_path)
    out["table_count"] = len(snap.tables)
    return out
