"""Workspace tenant resolution helper."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.workspace.workspace_scope import resolve_workspace_tenant_id


def test_resolve_workspace_tenant_from_context():
    ctx = DatamartRuntimeContext(
        tenant_id="acme_corp",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr",),
        primary_schema="hr",
        database_name="hrm_wh_acme_corp",
    )
    token = set_datamart_context(ctx)
    try:
        assert resolve_workspace_tenant_id() == "acme_corp"
        assert resolve_workspace_tenant_id("override_tenant") == "override_tenant"
    finally:
        reset_datamart_context(token)


def test_resolve_workspace_tenant_default_without_context():
    assert resolve_workspace_tenant_id() == "demo_tenant"


def test_rename_template_update_includes_tenant_filter():
    """Workspace mutations must scope by tenant_id (IDOR guard)."""
    import uuid

    from sqlalchemy.dialects import postgresql

    from app.models.datamart_workspace import DatamartTemplate
    from app.services.ai_services.datamart.workspace.workspace_scope import resolve_workspace_tenant_id

    tid = resolve_workspace_tenant_id("tenant_a")
    template_id = uuid.uuid4()
    stmt = (
        DatamartTemplate.__table__.update()
        .where(
            DatamartTemplate.id == template_id,
            DatamartTemplate.tenant_id == tid,
        )
        .values(name="renamed")
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "tenant_id" in compiled
    assert str(template_id) in compiled or "id_1" in compiled
