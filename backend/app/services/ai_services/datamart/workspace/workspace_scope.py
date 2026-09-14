"""Resolve tenant_id for platform DB workspace rows (sessions, templates)."""
from __future__ import annotations

from typing import Optional

from ..config import DATAMART_DEFAULT_TENANT_ID


def resolve_workspace_tenant_id(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit.strip()
    from .runtime_context import get_datamart_context

    ctx = get_datamart_context()
    if ctx is not None:
        return ctx.tenant_id
    return DATAMART_DEFAULT_TENANT_ID
