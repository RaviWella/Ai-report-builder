"""DataHub URN filtering for tenant ETL vs legacy profiles."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai_services.datamart.semantic.datahub_scope import filter_urns_for_datamart_context
from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)

_LEGACY_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "warehouse.public_mint_audit.dim_employee,PROD)"
)
_ETL_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "hrm_wh_demo_tenant.hr_semantic.vw_headcount,PROD)"
)
_WRONG_SCHEMA_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "hrm_wh_demo_tenant.hr_raw.stg_employee,PROD)"
)


def _ctx(profile: DatamartProfile) -> DatamartRuntimeContext:
    if profile == DatamartProfile.TENANT_ETL:
        return DatamartRuntimeContext(
            tenant_id="demo_tenant",
            profile=profile,
            engine=MagicMock(),
            query_schemas=("hr_semantic", "hr", "hr_snap"),
            primary_schema="hr_semantic",
            database_name="hrm_wh_demo_tenant",
        )
    return DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=profile,
        engine=MagicMock(),
        query_schemas=("public_mint_audit",),
        primary_schema="public_mint_audit",
        database_name="warehouse",
    )


def test_filter_legacy_keeps_audit_schema():
    token = set_datamart_context(_ctx(DatamartProfile.LEGACY_AUDIT))
    try:
        out = filter_urns_for_datamart_context([_LEGACY_URN, _ETL_URN])
        assert _LEGACY_URN in out
        assert _ETL_URN not in out
    finally:
        reset_datamart_context(token)


def test_filter_tenant_etl_keeps_semantic_schema():
    token = set_datamart_context(_ctx(DatamartProfile.TENANT_ETL))
    try:
        out = filter_urns_for_datamart_context([_ETL_URN, _LEGACY_URN, _WRONG_SCHEMA_URN])
        assert _ETL_URN in out
        assert _LEGACY_URN not in out
        assert _WRONG_SCHEMA_URN not in out
    finally:
        reset_datamart_context(token)
