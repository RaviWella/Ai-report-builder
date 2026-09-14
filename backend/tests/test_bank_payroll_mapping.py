"""Regression tests for bank-payment source mappings."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.hr_etl.source_mapping import load_source_mapping


def test_bank_payment_logical_pk_mappings():
    """MintHRM uses table-specific PK column names — never assume generic `id`."""
    m = load_source_mapping(profile="minthrm", variant="mysql")
    assert m.physical_col("payroll_salary_retrieve", "id") == "retrieve_id"
    assert m.physical_col("payroll_salary_bank_data", "id") == "bank_id"
    assert m.physical_col("payroll_salary_bank_data", "bank_id") == "bank_name"
    assert m.physical_col("payroll_bank", "id") == "id"
    assert m.physical_col("payroll_bank_branch", "id") == "id"


def test_bank_payment_columns_exist_on_live_mysql():
    """Optional live check — set RUN_MYSQL_MAPPING_INTEGRATION=1 with backend/.env configured."""
    if os.environ.get("RUN_MYSQL_MAPPING_INTEGRATION") != "1":
        pytest.skip("Set RUN_MYSQL_MAPPING_INTEGRATION=1 to validate against live MySQL")

    from tools.validate_source_mappings import validate_mapping
    from tools.validate_source_mappings import _mysql_url_from_env
    from sqlalchemy import create_engine

    engine = create_engine(_mysql_url_from_env())
    issues = validate_mapping("minthrm", "mysql", engine)
    assert issues == [], "\n".join(issues)
