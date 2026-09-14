"""Tests for MySQL keyset-chunk extract helpers."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import OperationalError

from app.services.hr_etl.extractors import (
    _apply_incremental_filter,
    _resolve_pk_column,
    _track_watermark,
)
from app.services.hr_etl.mysql_extract import (
    is_transient_mysql_error,
    wrap_keyset_chunk_sql,
)


def test_wrap_keyset_chunk_sql():
    inner = "SELECT 1 AS id FROM t"
    wrapped = wrap_keyset_chunk_sql(inner, "id")
    assert "WHERE id > :_chunk_after" in wrapped
    assert "ORDER BY id" in wrapped
    assert "LIMIT :_chunk_limit" in wrapped
    assert inner in wrapped


def test_is_transient_mysql_error_from_operational_error():
    class Orig(Exception):
        args = (2013, "Lost connection to MySQL server during query")

    exc = OperationalError("stmt", {}, Orig())
    assert is_transient_mysql_error(exc) is True


def test_is_transient_mysql_error_rejects_other():
    assert is_transient_mysql_error(ValueError("nope")) is False


def test_track_watermark_picks_latest():
    t1 = datetime(2024, 1, 1)
    t2 = datetime(2024, 6, 1)
    row = {"updated_at": t2}
    result = _track_watermark(row, "updated_at", t1)
    assert result == t2


def test_resolve_pk_column_defaults_to_id():
    column_map = [("id", None), ("name", None)]
    assert _resolve_pk_column(column_map, None) == "id"
    assert _resolve_pk_column(column_map, "custom_id") == "custom_id"


def test_resolve_pk_column_none_without_id():
    column_map = [("code", None), ("name", None)]
    assert _resolve_pk_column(column_map, None) is None


def test_apply_incremental_filter_pk_mode():
    from unittest.mock import MagicMock

    pg = MagicMock()
    pg.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = 42
    sql = "SELECT 1 AS id FROM t"
    params: dict = {}
    out = _apply_incremental_filter(
        pg,
        sql,
        params,
        incremental=True,
        pk_column="id",
        watermark_col="updated_at",
        target_table="stg_prl_overtime",
        tenant_id="demo",
        incremental_by_pk=True,
    )
    assert "WHERE id > :_last_pk" in out
    assert params["_last_pk"] == 42
