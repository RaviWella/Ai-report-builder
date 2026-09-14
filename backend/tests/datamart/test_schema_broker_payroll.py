"""Schema broker includes enough payroll tables for summary reports."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.ai_services.datamart.schema_broker import (
    _broker_table_cap,
    _merge_table_names,
    _prioritize_table_names,
)
from app.services.ai_services.datamart.semantic.semantic_catalog_paths import tenant_catalog_path
from app.services.ai_services.datamart.semantic.semantic_layer import (
    clear_catalog_cache,
    resolve_semantics,
)


def setup_function() -> None:
    clear_catalog_cache()


def test_payroll_question_prioritizes_summary_view():
    q = (
        "Prepare a payroll summary report by combining employee, payroll group, "
        "and employee snapshot details. Include employee name, employee ID, "
        "payroll group name, pay frequency, currency code, branch, and current basic salary."
    )
    demo_path = tenant_catalog_path("demo_tenant")
    with patch(
        "app.services.ai_services.datamart.semantic.semantic_layer.resolve_semantic_catalog_path",
        return_value=demo_path,
    ):
        sem = resolve_semantics(q)
    assert "payroll" in sem.topics_matched
    ordered = _prioritize_table_names(q, sem.seed_tables, sem.topics_matched)
    assert ordered[0] == "vw_payroll_summary"
    assert "dim_payroll_group" in ordered[:6]
    assert "dim_employee" in ordered[:6]
    assert "payroll_group_name" in sem.prompt_block
    assert "payroll_frequency" in sem.prompt_block or "pay frequency" in sem.prompt_block


def test_payroll_topic_gets_higher_table_cap():
    q = "payroll summary by branch"
    sem = resolve_semantics(q)
    assert _broker_table_cap(sem, q) >= 8
    merged = _merge_table_names(
        _prioritize_table_names(q, sem.seed_tables, sem.topics_matched),
        max_tables=_broker_table_cap(sem, q),
    )
    assert "vw_payroll_summary" in merged
    assert len(merged) >= 5
