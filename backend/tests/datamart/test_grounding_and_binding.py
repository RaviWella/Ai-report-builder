"""Unit tests for schema broker and SQL binding (no warehouse connection)."""
from app.services.ai_services.datamart.schema_broker import (
    SchemaGrounding,
    _columns_from_datahub_text,
    _merge_table_names,
    _rank_tables_by_keywords,
)
from app.services.ai_services.datamart.sql.sql_binding import validate_sql_bindings


def _grounding() -> SchemaGrounding:
    return SchemaGrounding(
        columns_by_table={
            "public_mint_audit.dim_employee": [
                "employee_id",
                "full_name",
                "branch",
                "legal_entity",
            ],
        },
        join_hint_lines=[],
        source="test",
    )


def test_columns_from_datahub_text_parser():
    text = (
        "Table: public_mint_audit.dim_employee\n"
        "  Columns: employee_id, full_name, branch\n"
    )
    parsed = _columns_from_datahub_text(text)
    assert "public_mint_audit.dim_employee" in parsed
    assert parsed["public_mint_audit.dim_employee"] == ["employee_id", "full_name", "branch"]


def test_rank_tables_by_keywords():
    tables = ["dim_employee", "fact_payroll_detail", "dim_calendar"]
    ranked = _rank_tables_by_keywords("employee workforce branch", tables, 2)
    assert ranked[0] == "dim_employee"


def test_merge_table_names_dedupes():
    merged = _merge_table_names(["dim_employee", "fact_x"], ["dim_employee", "dim_org"])
    assert merged == ["dim_employee", "fact_x", "dim_org"]


def test_binding_accepts_valid_sql():
    g = _grounding()
    sql = (
        "SELECT full_name, employee_id FROM public_mint_audit.dim_employee "
        "WHERE branch = 'HQ' LIMIT 10;"
    )
    assert validate_sql_bindings(sql, g) is None


def test_binding_rejects_unknown_column():
    g = _grounding()
    sql = (
        "SELECT imaginary_col FROM public_mint_audit.dim_employee LIMIT 10;"
    )
    err = validate_sql_bindings(sql, g)
    assert err is not None
    assert "imaginary_col" in err.lower() or "allowlist" in err.lower()


def test_binding_rejects_unknown_table():
    g = _grounding()
    sql = "SELECT * FROM public_mint_audit.not_a_real_table LIMIT 1;"
    err = validate_sql_bindings(sql, g)
    assert err is not None
    assert "not_a_real_table" in err.lower() or "allowlist" in err.lower()


def test_grounding_prompt_lists_tables():
    g = _grounding()
    text = g.to_prompt_text()
    assert "public_mint_audit.dim_employee" in text
    assert "employee_id" in text
    assert "allowlist" in text.lower()
