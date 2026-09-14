"""Retry prompt carries cumulative attempt history."""
from app.services.ai_services.datamart.prompts.simple_prompts import (
    SqlAttemptRecord,
    build_simple_retry_prompt,
)


def test_retry_prompt_includes_prior_attempts_and_guidance():
    prior = [
        SqlAttemptRecord(
            attempt=1,
            failed_sql="SELECT 1 FROM hr.fact_leave_transaction fl",
            error="operator does not exist: text = integer",
            issue_kind="join_type_mismatch",
            user_hint="Join keys use incompatible types.",
            llm_guidance="Use emp_no not employee_sk for approver.",
            action_taken="expand_context",
            tables_added=("vw_pending_leave_approvals",),
        )
    ]
    prompt = build_simple_retry_prompt(
        question="Pending leave approvals",
        failed_sql="SELECT 2",
        error_message="column foo does not exist",
        mappings_text="(mappings)",
        datahub_text="(datahub)",
        schema_text="(schema)",
        attempt=2,
        prior_attempts=prior,
        llm_guidance="Use only listed columns.",
        tables_added_this_retry=["fact_leave_transaction"],
    )
    assert "Prior failed attempts" in prompt
    assert "Attempt 1 (join_type_mismatch)" in prompt
    assert "vw_pending_leave_approvals" in prompt
    assert "Use emp_no not employee_sk" in prompt
    assert "attempt 2/4" in prompt
    assert "cumulative introspection" in prompt
    assert "Fix ONLY" in prompt
