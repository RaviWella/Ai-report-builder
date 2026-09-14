"""Filter DataHub dataset URNs to the active datamart warehouse context."""
from __future__ import annotations

import logging
from typing import Optional

from ..workspace.runtime_context import get_datamart_context

logger = logging.getLogger("ai_services.datamart.datahub")


def _schema_table_from_urn(urn: str) -> Optional[tuple[str, str]]:
    """
    Parse URN dataset segment into (schema, table).

    Examples:
      warehouse.public_mint_audit.dim_employee
      hrm_wh_demo_tenant.hr_semantic.vw_headcount
    """
    try:
        dataset_part = urn.split(",")[1]
    except (IndexError, AttributeError):
        return None
    segments = [s.strip() for s in dataset_part.split(".") if s.strip()]
    if len(segments) < 2:
        return None
    return segments[-2].lower(), segments[-1].lower()


def filter_urns_for_datamart_context(urns: list[str]) -> list[str]:
    """
    Keep URNs whose schema is in the active query_schemas allowlist.

    When no runtime context is set, returns URNs unchanged (legacy behaviour).
    """
    ctx = get_datamart_context()
    if ctx is None:
        return urns

    allowed = ctx.allowed_schemas_lower
    db_name = (ctx.database_name or "").strip().lower()
    out: list[str] = []
    for urn in urns:
        parsed = _schema_table_from_urn(urn)
        if not parsed:
            continue
        schema, _table = parsed
        if schema not in allowed:
            continue
        if ctx.is_tenant_etl and db_name:
            try:
                dataset_part = urn.split(",")[1].lower()
                if db_name not in dataset_part and not dataset_part.startswith("warehouse."):
                    logger.debug("DataHub URN skipped (db mismatch): %s", urn)
                    continue
            except (IndexError, AttributeError):
                pass
        out.append(urn)
    if len(out) < len(urns):
        logger.debug(
            "DataHub URNs filtered %d -> %d for tenant=%s schemas=%s",
            len(urns),
            len(out),
            ctx.tenant_id,
            ",".join(ctx.query_schemas),
        )
    return out
