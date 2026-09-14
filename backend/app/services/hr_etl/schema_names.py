"""Resolve warehouse schema names for a tenant."""
from __future__ import annotations

from app.core.warehouse import get_layout_sync


def raw_schema(tenant_id: str) -> str:
    return get_layout_sync(tenant_id).raw_schema


def mart_schema(tenant_id: str) -> str:
    return get_layout_sync(tenant_id).mart_schema


def semantic_schema(tenant_id: str) -> str:
    return get_layout_sync(tenant_id).semantic_schema


def custom_reports_schema(tenant_id: str) -> str:
    return get_layout_sync(tenant_id).custom_reports_schema


def control_schema(tenant_id: str) -> str:
    return get_layout_sync(tenant_id).control_schema
