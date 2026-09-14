"""Strict multi-table binding requires qualified columns."""
from app.services.ai_services.datamart import config as dm_config
from app.services.ai_services.datamart.schema_broker import SchemaGrounding
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings


def test_strict_rejects_unqualified_column(monkeypatch):
    monkeypatch.setattr(dm_config, "DATAMART_VALIDATION_STRICT_BINDING", True)
    grounding = SchemaGrounding(
        columns_by_table={
            "public_mint_audit.dim_employee": ["employee_id", "full_name"],
            "public_mint_audit.fact_payroll_detail": ["employee_id", "basic_salary"],
        },
        source="test",
    )
    sql = """
    SELECT employee_id, basic_salary
    FROM public_mint_audit.dim_employee e
    JOIN public_mint_audit.fact_payroll_detail p ON e.employee_id = p.employee_id
    """
    err = validate_sql_bindings(sql, grounding)
    assert err is not None
    assert "alias" in err.lower()


def test_strict_allows_qualified_columns(monkeypatch):
    monkeypatch.setattr(dm_config, "DATAMART_VALIDATION_STRICT_BINDING", True)
    grounding = SchemaGrounding(
        columns_by_table={
            "public_mint_audit.dim_employee": ["employee_id", "full_name"],
            "public_mint_audit.fact_payroll_detail": ["employee_id", "basic_salary"],
        },
        source="test",
    )
    sql = """
    SELECT e.employee_id, p.basic_salary
    FROM public_mint_audit.dim_employee e
    JOIN public_mint_audit.fact_payroll_detail p ON e.employee_id = p.employee_id
    """
    assert validate_sql_bindings(sql, grounding) is None
