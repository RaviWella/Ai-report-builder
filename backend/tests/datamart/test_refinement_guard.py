"""Follow-up SQL must preserve prior columns unless user asks to drop them."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.orchestration.refinement_guard import check_refinement_preserves_sql

PRIOR = """
SELECT a AS employee_name, b AS branch, c AS leave_type
FROM hr.fact_leave_transaction
LIMIT 100
"""

NARROWED = """
SELECT a AS employee_name
FROM hr.fact_leave_transaction
LIMIT 100
"""


def test_blocks_silent_column_drop_on_refine():
    err = check_refinement_preserves_sql(
        question="filter to branch Colombo only",
        prior_sql=PRIOR,
        new_sql=NARROWED,
        chat_intent=ChatIntent.REFINE_SQL,
    )
    assert err is not None
    assert "branch" in err.lower() or "column" in err.lower()


def test_allows_explicit_column_removal():
    err = check_refinement_preserves_sql(
        question="remove the branch column from the report",
        prior_sql=PRIOR,
        new_sql=NARROWED,
        chat_intent=ChatIntent.REFINE_SQL,
    )
    assert err is None
