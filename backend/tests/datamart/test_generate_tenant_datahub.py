"""Phase 6b — tenant DataHub ingest recipe generation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ai_services.datamart.workspace.runtime_context import DatamartProfile


def test_build_recipe_yaml_includes_etl_schemas():
    from tools.generate_tenant_datahub_ingest import build_recipe_yaml

    ctx = MagicMock()
    ctx.profile = DatamartProfile.TENANT_ETL
    ctx.query_schemas = ("hr_semantic", "hr", "hr_snap")

    with patch(
        "tools.generate_tenant_datahub_ingest.resolve_datamart_context",
        return_value=ctx,
    ), patch(
        "app.core.warehouse.connection_params",
        return_value={
            "host": "wh.example.com",
            "port": 5432,
            "database": "hrm_wh_demo_tenant",
            "user": "reader",
            "password": "secret",
        },
    ):
        yaml_text = build_recipe_yaml(tenant_id="demo_tenant")

    assert "hrm_wh_demo_tenant" in yaml_text
    assert "hr_semantic" in yaml_text
    assert "hr_snap" in yaml_text
    assert "host_port:" in yaml_text
