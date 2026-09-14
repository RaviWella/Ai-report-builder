"""Unit tests for the source-discovery layer classifier (pure, DB-free)."""

from app.services.source_discovery import _layer, _norm


def test_layer_classification_by_prefix():
    assert _layer("mart_daily_attendance") == ("mart", 0)
    assert _layer("fct_daily_attendance") == ("fact", 1)
    assert _layer("fact_attendance") == ("fact", 1)
    assert _layer("dim_shift") == ("dimension", 1)
    assert _layer("stg_attendance") == ("staging", 2)
    assert _layer("random_table")[0] == "other"


def test_layer_depth_orders_mart_closest():
    assert _layer("mart_x")[1] < _layer("fct_x")[1] < _layer("stg_x")[1]


def test_norm_collapses_punctuation():
    assert _norm("Punch In Location") == "punch in location"
    assert _norm("shift_name") == "shift name"
