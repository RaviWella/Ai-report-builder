"""Unit tests for dialect-aware SQL builders."""
from __future__ import annotations

import pytest

from app.services.hr_etl.source_connection import source_dialect
from app.services.hr_etl import sql_dialect as sd


@pytest.mark.parametrize(
    "dialect,fn,expected_substr",
    [
        ("mysql", sd.sql_substring_index, "SUBSTRING_INDEX"),
        ("postgres", sd.sql_substring_index, "split_part"),
        ("mysql", sd.sql_hash_mod_int, "CRC32"),
        ("postgres", sd.sql_hash_mod_int, "hashtext"),
        ("mysql", sd.sql_date_diff_inclusive, "DATEDIFF"),
        ("postgres", sd.sql_date_diff_inclusive, "::date"),
        ("mysql", sd.sql_concat, "CONCAT"),
        ("postgres", sd.sql_concat, " || "),
        ("mysql", sd.sql_payroll_run_code, "CONCAT"),
        ("postgres", sd.sql_payroll_run_code, " || "),
    ],
)
def test_dialect_fragments(dialect, fn, expected_substr):
    with source_dialect(dialect):
        if fn is sd.sql_substring_index:
            sql = fn("col", " ", 1)
        elif fn is sd.sql_hash_mod_int:
            sql = fn("col")
        elif fn is sd.sql_date_diff_inclusive:
            sql = fn("a", "b")
        elif fn is sd.sql_concat:
            sql = fn("'x'", "col")
        elif fn is sd.sql_payroll_run_code:
            sql = fn("g", "y", "m", "h")
        else:
            sql = fn()
        assert expected_substr in sql


def test_substring_index_last_segment_postgres():
    with source_dialect("postgres"):
        sql = sd.sql_substring_index("b.emp_name", " ", -1)
    assert "regexp_split_to_array" in sql


def test_qident_reserved_word():
    with source_dialect("postgres"):
        assert sd.qident("date") == '"date"'
    with source_dialect("mysql"):
        assert sd.qident("date") == "`date`"
