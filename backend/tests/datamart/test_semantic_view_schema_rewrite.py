"""Semantic view schema rewrite for tenant ETL warehouses."""
from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    DatamartRuntimeContext,
    reset_datamart_context,
    set_datamart_context,
)
from app.services.ai_services.datamart.sql.sql_table_normalize import rewrite_semantic_view_schema


def test_rewrite_hr_vw_to_semantic():
    ctx = DatamartRuntimeContext(
        tenant_id="demo",
        profile=DatamartProfile.TENANT_ETL,
        engine=None,  # type: ignore[arg-type]
        query_schemas=("hr_semantic", "hr", "hr_snap"),
        primary_schema="hr_semantic",
        database_name="hrm_wh_demo",
    )
    token = set_datamart_context(ctx)
    try:
        sql = (
            "SELECT v.emp_fullname FROM hr.vw_payroll_summary v "
            "JOIN hr.dim_payroll_group pg ON 1=1 LIMIT 10"
        )
        out = rewrite_semantic_view_schema(sql)
        assert "hr_semantic.vw_payroll_summary" in out.lower()
        assert "hr.dim_payroll_group" in out.lower()
    finally:
        reset_datamart_context(token)
