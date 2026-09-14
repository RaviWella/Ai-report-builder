"""Attendance topic retrieval and catalog SQL."""
from app.services.ai_services.datamart.domain_sql.catalog_report_sql import (
    looks_like_attendance_summary,
    try_build_attendance_summary_sql,
)
from app.services.ai_services.datamart.schema_broker import build_schema_grounding, BrokerMode
from app.services.ai_services.datamart.semantic.semantic_layer import (
    required_tables_for_question,
    resolve_semantics,
)

ATTENDANCE_Q = "Show attendance summary for this month"


def test_attendance_summary_detected():
    assert looks_like_attendance_summary(ATTENDANCE_Q)


def test_attendance_summary_template_uses_view():
    sql = try_build_attendance_summary_sql(ATTENDANCE_Q)
    assert sql is not None
    assert "vw_attendance_summary" in sql
    assert "TO_CHAR(CURRENT_DATE, 'YYYY-MM')" in sql


def test_required_tables_include_attendance_facts():
    required = required_tables_for_question(ATTENDANCE_Q)
    assert "fact_attendance" in required
    assert "vw_attendance_summary" in required


def test_semantics_match_attendance_not_only_payroll():
    """Payroll topic must not win when the question is clearly about attendance."""
    semantics = resolve_semantics(ATTENDANCE_Q)
    assert "attendance" in semantics.topics_matched
    assert "payroll" not in semantics.topics_matched


def test_broker_must_include_prioritizes_attendance_tables(monkeypatch):
    """Broker seeds must-include tables before the table cap drops them."""

    def fake_finalize(selected, **kwargs):
        from app.services.ai_services.datamart.schema_broker import SchemaGrounding

        col_map = {}
        for name in selected:
            col_map[f"hr.{name}"] = ["id"]
        return SchemaGrounding(columns_by_table=col_map, source=kwargs.get("source", "test"))

    monkeypatch.setattr(
        "app.services.ai_services.datamart.schema_broker._finalize_grounding",
        fake_finalize,
    )
    monkeypatch.setattr(
        "app.services.ai_services.datamart.schema_broker.search_relevant_tables",
        lambda _q: [],
    )
    monkeypatch.setattr(
        "app.services.ai_services.datamart.schema_broker.list_warehouse_tables",
        lambda: [
            "vw_payroll_summary",
            "dim_employee",
            "fact_attendance",
            "vw_attendance_summary",
        ],
    )

    grounding = build_schema_grounding(question=ATTENDANCE_Q, mode=BrokerMode.CHAT)
    shorts = {s.lower() for s in grounding.table_short_names}
    assert "fact_attendance" in shorts
    assert "vw_attendance_summary" in shorts
