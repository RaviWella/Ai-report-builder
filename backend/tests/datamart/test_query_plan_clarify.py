"""Query plan clarification extraction."""
from app.services.ai_services.datamart.pipeline.artifacts import QueryPlan
from app.services.ai_services.datamart.pipeline.query_plan import clarification_from_plan


def test_clarification_from_plan():
    plan = QueryPlan(
        filters=["NEEDS_CLARIFICATION: Which payroll period should I use?"],
    )
    assert clarification_from_plan(plan) == "Which payroll period should I use?"

    assert clarification_from_plan(QueryPlan(filters=["status = active"])) is None
