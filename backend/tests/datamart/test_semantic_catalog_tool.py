"""Unit tests for semantic_catalog_tool refresh logic (no warehouse)."""
from tools.semantic_catalog_tool import (
    WarehouseSnapshot,
    _infer_topic_for_table,
    _schema_introspection_order,
    refresh_catalog,
    validate_catalog,
)


def _snap() -> WarehouseSnapshot:
    return WarehouseSnapshot(
        schema="public_mint_audit",
        tables=["dim_employee", "fact_payroll_detail"],
        columns_by_table={
            "dim_employee": {"employee_id", "full_name", "legal_entity"},
            "fact_payroll_detail": {"employee_id", "basic_salary", "job_title"},
        },
        foreign_keys=[
            {
                "left_table": "fact_payroll_detail",
                "left_column": "employee_id",
                "right_table": "dim_employee",
                "right_column": "employee_id",
            },
        ],
    )


def test_validate_flags_missing_table():
    catalog = {
        "topics": {"payroll": {"tables": ["fact_missing"]}},
        "dimensions": {},
        "metrics": {},
        "joins": [],
    }
    report = validate_catalog(catalog, _snap())
    assert "fact_missing" in report["missing_tables"]


def test_refresh_removes_stale_dimension():
    catalog = {
        "topics": {"payroll": {"keywords": ["pay"], "tables": ["fact_payroll_detail"]}},
        "dimensions": {
            "old_col": {"table": "dim_employee", "column": "removed_column", "synonyms": ["x"]},
            "company": {"table": "dim_employee", "column": "legal_entity", "synonyms": ["company"]},
        },
        "metrics": {},
        "joins": [],
    }
    report = refresh_catalog(catalog, _snap())
    assert "old_col" in report.removed_dimensions
    assert "company" in catalog["dimensions"]
    assert "old_col" not in catalog["dimensions"]


def test_infer_topic_semantic_view():
    assert _infer_topic_for_table("vw_headcount", {}) == "semantic_views"


def test_infer_topic_snap_table():
    assert _infer_topic_for_table("snap_employee_daily", {}) == "past_data"


def test_schema_introspection_order_prefers_hr_mart():
    order = _schema_introspection_order(("hr_snap", "hr_semantic", "hr"))
    assert order[0] == "hr"
    assert "hr_semantic" in order
    assert order[-1] == "hr_snap"


def test_refresh_adds_new_table_to_topic():
    snap = _snap()
    snap.tables.append("fact_leave_transaction")
    snap.columns_by_table["fact_leave_transaction"] = {"employee_id", "leave_days"}
    catalog = {
        "topics": {"leave": {"keywords": ["leave"], "tables": []}},
        "dimensions": {},
        "metrics": {},
        "joins": [],
    }
    report = refresh_catalog(catalog, snap)
    assert "fact_leave_transaction" in catalog["topics"]["leave"]["tables"]
    assert "fact_leave_transaction" in report.topics_tables_added.get("leave", [])
