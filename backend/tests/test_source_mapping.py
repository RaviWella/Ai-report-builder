"""Tests for YAML source mapping loader."""
from __future__ import annotations

from app.services.hr_etl.source_connection import source_dialect
from app.services.hr_etl.source_mapping import load_source_mapping, source_mapping


def test_load_minthrm_mysql_mapping():
    m = load_source_mapping(profile="minthrm", variant="mysql")
    assert m.table("emp_basic") in ("hr_empbasic", "`hr_empbasic`")
    assert m.physical_col("emp_basic", "id") == "emp_id"
    assert m.physical_col("payroll_salary_bank_data", "id") == "bank_id"


def test_mapping_context_ref():
    with source_dialect("mysql"), source_mapping("demo_tenant", "mysql"):
        from app.services.hr_etl.source_mapping import get_source_mapping

        m = get_source_mapping()
        assert m.ref("emp_basic", "employee_code", "b") == "b.emp_no"


def test_tenant_override_merge(tmp_path, monkeypatch):
    import app.services.hr_etl.source_mapping as sm

    base = tmp_path / "minthrm_mysql.yaml"
    base.write_text(
        "tables:\n  emp_basic: hr_empbasic\n"
        "columns:\n  emp_basic:\n    id: emp_id\n",
        encoding="utf-8",
    )
    override_dir = tmp_path / "overrides"
    override_dir.mkdir()
    (override_dir / "acme.yaml").write_text(
        "columns:\n  emp_basic:\n    id: employee_id\n", encoding="utf-8"
    )
    monkeypatch.setattr(sm, "_MAPPINGS_DIR", tmp_path)
    m = load_source_mapping(profile="minthrm", variant="mysql", tenant_id="acme")
    assert m.physical_col("emp_basic", "id") == "employee_id"
