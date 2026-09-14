"""Add-scenario history isolation."""
from app.services.ai_services.datamart.scenario.scenario_history import format_add_scenario_history
from app.services.ai_services.datamart.scenario.scenario_pipeline import recover_add_scenario_specs
from app.services.ai_services.datamart.sql.sql_generation import SqlGenerationOutcome


def test_format_add_scenario_history_strips_sql():
    history = (
        "User: Top salaries\n\n"
        "Assistant: Here are results.\n\n"
        "[SQL turn 1]\n```sql\nSELECT emp FROM hr.mart_employee_current\n```"
    )
    out = format_add_scenario_history(history)
    assert "SELECT emp" not in out
    assert "ADDITIONAL_RESULT_BLOCKS" in out


def test_recover_add_scenario_specs_from_repair(monkeypatch):
    from app.services.ai_services.datamart import scenario_pipeline as sp

    class _G:
        table_short_names = ["fact_recruitment_pipeline"]

    monkeypatch.setattr(
        sp,
        "recover_sql_after_llm",
        lambda **_: SqlGenerationOutcome(
            sql="SELECT candidate_id FROM hr.fact_recruitment_pipeline",
            narrative="Recruitment list",
            post_process_config=None,
            source="repair_missing",
        ),
    )
    specs = recover_add_scenario_specs(
        question="Recruitment pipeline",
        narrative="",
        llm_output="NARRATIVE:\nNo sql here.",
        sql=None,
        post_process_config=None,
        grounding=_G(),  # type: ignore[arg-type]
        history_text="(No previous messages)",
    )
    assert len(specs) == 1
    assert "SELECT" in specs[0]["sql"]
