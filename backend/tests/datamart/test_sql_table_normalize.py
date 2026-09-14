"""Database.catalog.table normalization for tenant ETL SQL."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_table_normalize import (
    binding_error_for_database_catalog,
    strip_database_catalog_prefix,
)


def _ctx() -> DatamartRuntimeContext:
    return DatamartRuntimeContext(
        tenant_id="demo_tenant",
        profile=DatamartProfile.TENANT_ETL,
        engine=MagicMock(),
        query_schemas=("hr_semantic", "hr", "hr_snap"),
        primary_schema="hr_semantic",
        database_name="hrm_wh_demo_tenant",
    )


def test_strip_database_catalog_prefix():
    token = set_datamart_context(_ctx())
    try:
        sql = (
            "SELECT e.emp_fullname FROM hrm_wh_demo_tenant.hr.mart_employee_current e "
            "JOIN hrm_wh_demo_tenant.hr.dim_employee de ON e.employee_sk = de.employee_sk "
            "LIMIT 10"
        )
        out = strip_database_catalog_prefix(sql)
        assert "hrm_wh_demo_tenant.hr." not in out.lower()
        assert "hr.mart_employee_current" in out.lower()
        assert "hr.dim_employee" in out.lower()
    finally:
        reset_datamart_context(token)


def test_binding_rejects_database_catalog_prefix():
    token = set_datamart_context(_ctx())
    try:
        sql = "SELECT 1 FROM hrm_wh_demo_tenant.hr.mart_employee_current LIMIT 1"
        err = binding_error_for_database_catalog(sql)
        assert err is not None
        assert "do not prefix" in err.lower()

        grounding = SchemaGrounding(
            columns_by_table={"hr.mart_employee_current": ["emp_fullname"]},
            source="test",
        )
        assert validate_sql_bindings(sql, grounding) is not None
    finally:
        reset_datamart_context(token)
