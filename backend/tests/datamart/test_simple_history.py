"""Mode-aware history shaping for simplified datamart chat."""
from app.services.ai_services.datamart.models import FollowUpMode
from app.services.ai_services.datamart.prompts.simple_history import prepare_simple_turn_context

_SAMPLE_HISTORY = """
User: Show headcount by department
Assistant: Here is headcount by department.

[SQL turn 1]
```sql
SELECT department, COUNT(*) FROM hr.mart_employee_current GROUP BY 1
```

User: Add bank details
Assistant: Added bank columns.

[SQL turn 2]
```sql
SELECT emp_no, bank_name FROM hr.mart_employee_current
```
"""


def test_modify_mode_keeps_last_dialogue_not_full_sql():
    turn = prepare_simple_turn_context(
        question="filter active only",
        history_text=_SAMPLE_HISTORY,
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
        previous_primary_sql="SELECT department, COUNT(*) FROM hr.mart_employee_current GROUP BY 1",
    )
    assert turn.is_modify
    assert "GROUP BY 1" in (turn.anchor_sql or "")
    assert "emp_no, bank_name" not in turn.history_for_prompt
    assert "filter active only" not in turn.history_for_prompt
    assert "Add bank details" in turn.history_for_prompt


def test_add_scenario_strips_prior_sql():
    turn = prepare_simple_turn_context(
        question="List leave balances",
        history_text=_SAMPLE_HISTORY,
        follow_up_mode=FollowUpMode.ADD_SCENARIO,
    )
    assert turn.is_add_scenario
    assert "```sql" not in turn.history_for_prompt
    assert "Add scenario" in turn.mode_instructions or "scenario" in turn.mode_instructions.lower()


def test_new_question_strips_sql():
    turn = prepare_simple_turn_context(
        question="What is average salary?",
        history_text=_SAMPLE_HISTORY,
        follow_up_mode=FollowUpMode.NEW_QUESTION,
    )
    assert turn.is_new_question
    assert "```sql" not in turn.history_for_prompt
    assert "new" in turn.mode_instructions.lower()
