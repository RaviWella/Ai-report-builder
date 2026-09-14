"""Multi-schema SQL binding for tenant ETL profile."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings


def _etl_context() -> DatamartRuntimeContext:
    return DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr_semantic", "hr", "hr_snap"),
        primary_schema="hr_semantic",
        database_name="hrm_wh_demo_tenant",
    )


def test_binding_allows_hr_semantic_and_hr():
    token = set_datamart_context(_etl_context())
    try:
        grounding = SchemaGrounding(
            columns_by_table={
                "hr_semantic.vw_headcount": ["employee_id", "branch_id"],
                "hr.dim_employee": ["employee_id", "full_name"],
            },
            source="test",
        )
        sql = (
            "SELECT h.employee_id, e.full_name "
            "FROM hr_semantic.vw_headcount h "
            "JOIN hr.dim_employee e ON h.employee_id = e.employee_id "
            "LIMIT 10"
        )
        assert validate_sql_bindings(sql, grounding) is None
    finally:
        reset_datamart_context(token)


def test_binding_rejects_unknown_schema():
    token = set_datamart_context(_etl_context())
    try:
        grounding = SchemaGrounding(
            columns_by_table={"hr.dim_employee": ["employee_id"]},
            source="test",
        )
        sql = "SELECT employee_id FROM public_mint_audit.dim_employee LIMIT 5"
        err = validate_sql_bindings(sql, grounding)
        assert err is not None
        assert "outside allowed" in err.lower() or "not in" in err.lower()
    finally:
        reset_datamart_context(token)
