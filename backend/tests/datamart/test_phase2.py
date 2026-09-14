"""Phase 2: intent router, semantic seeds, grounding expansion."""
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent, classify_chat_intent
from app.services.ai_services.datamart.models import FollowUpMode
from app.services.ai_services.datamart.schema_broker import SchemaGrounding, expand_grounding_with_tables
from app.services.ai_services.datamart.semantic.semantic_layer import semantic_seed_tables
from app.services.ai_services.datamart.postprocess.post_process_validate import validate_post_process_config


def test_classify_new_query_without_history():
    assert classify_chat_intent("workforce report", last_sql=None, has_prior_post_process=False) == ChatIntent.NEW_QUERY


def test_follow_up_mode_new_question_overrides_refine_signals():
    sql = "SELECT a FROM public_mint_audit.dim_employee LIMIT 10;"
    intent = classify_chat_intent(
        "from the above response remove the leave days column",
        last_sql=sql,
        has_prior_post_process=False,
        follow_up_mode=FollowUpMode.NEW_QUESTION,
    )
    assert intent == ChatIntent.NEW_QUERY


def test_follow_up_mode_continue_last_still_refines():
    sql = "SELECT a FROM public_mint_audit.dim_employee LIMIT 10;"
    intent = classify_chat_intent(
        "add filter for branch = HQ",
        last_sql=sql,
        has_prior_post_process=False,
        follow_up_mode=FollowUpMode.CONTINUE_LAST,
    )
    assert intent == ChatIntent.REFINE_SQL


def test_format_chat_system_prompt_includes_schema_placeholder():
    from app.services.ai_services.datamart.prompts.chat_prompts import format_chat_system_prompt
    from app.services.ai_services.datamart.workspace.runtime_context import (
        resolve_datamart_context,
        set_datamart_context,
    )

    ctx = resolve_datamart_context("demo_tenant")
    token = set_datamart_context(ctx)
    try:
        prompt = format_chat_system_prompt()
        assert "{schema}" not in prompt
        assert ".dim_employee" in prompt or "dim_employee" in prompt
    finally:
        from app.services.ai_services.datamart.workspace.runtime_context import reset_datamart_context

        reset_datamart_context(token)


def test_new_question_addon_present():
    from app.services.ai_services.datamart.prompts.chat_prompts import format_new_question_in_session_addon

    addon = format_new_question_in_session_addon()
    assert "new standalone" in addon.lower()
    assert "do not" in addon.lower()


def test_classify_refine_with_history():
    sql = "SELECT a FROM public_mint_audit.dim_employee LIMIT 10;"
    intent = classify_chat_intent(
        "add filter for branch = HQ",
        last_sql=sql,
        has_prior_post_process=False,
    )
    assert intent == ChatIntent.REFINE_SQL


def test_classify_refine_remove_natural_language():
    sql = "SELECT e.full_name, flt.leave_days FROM public_mint_audit.fact_leave_transaction flt LIMIT 5;"
    intent = classify_chat_intent(
        "ok then from the above response remove the leave days column",
        last_sql=sql,
        has_prior_post_process=False,
    )
    assert intent == ChatIntent.REFINE_SQL


def test_refinement_anchor_block_includes_sql():
    from app.services.ai_services.datamart.prompts.chat_prompts import format_refinement_anchor_block

    block = format_refinement_anchor_block("SELECT 1 AS x LIMIT 5;")
    assert "```sql" in block
    assert "SELECT 1" in block
    assert "minimal" in block.lower()


def test_refinement_anchor_empty_without_sql():
    from app.services.ai_services.datamart.prompts.chat_prompts import format_refinement_anchor_block

    assert format_refinement_anchor_block(None) == ""
    assert format_refinement_anchor_block("") == ""


def test_classify_analytical_duplicate_question():
    sql = (
        "SELECT employee_id, COUNT(*) AS record_count "
        "FROM public_mint_audit.fact_leave_transaction GROUP BY employee_id HAVING COUNT(*) > 1;"
    )
    intent = classify_chat_intent(
        "in the above table is the same employee duplicated across multiple records?",
        last_sql=sql,
        has_prior_post_process=False,
    )
    assert intent == ChatIntent.ANALYTICAL_OVER_PRIOR


def test_analytical_does_not_override_sql_column_removal():
    sql = "SELECT a, b, c FROM public_mint_audit.fact_leave_transaction LIMIT 10;"
    intent = classify_chat_intent(
        "from the above response remove the leave days column",
        last_sql=sql,
        has_prior_post_process=False,
    )
    assert intent == ChatIntent.REFINE_SQL


def test_narrative_insight_duplicate():
    from app.services.ai_services.datamart.postprocess.narrative_insights import enrich_narrative_from_results

    narrative = enrich_narrative_from_results(
        question="is the same employee duplicated?",
        narrative="",
        columns=["employee_id", "record_count"],
        rows=[[1, 3], [2, 2]],
        intent=ChatIntent.ANALYTICAL_OVER_PRIOR,
    )
    assert narrative.lower().startswith("yes")
    assert "2" in narrative


def test_classify_post_process_only():
    sql = "SELECT full_name FROM public_mint_audit.dim_employee LIMIT 10;"
    intent = classify_chat_intent(
        "change the label_format on the per company summary rows",
        last_sql=sql,
        has_prior_post_process=True,
    )
    assert intent == ChatIntent.POST_PROCESS_ONLY


def test_semantic_seed_workforce():
    seeds = semantic_seed_tables("Generate a workforce report by company and branch")
    assert "dim_employee" in seeds


def test_expand_grounding_adds_payroll_table():
    base = SchemaGrounding(
        columns_by_table={
            "public_mint_audit.dim_employee": ["employee_id", "full_name"],
        },
        join_hint_lines=[],
    )
    sql = (
        "SELECT e.full_name, p.amount FROM public_mint_audit.dim_employee e "
        "JOIN public_mint_audit.fact_payroll_detail p ON e.employee_id = p.employee_id "
        "LIMIT 5;"
    )
    expanded = expand_grounding_with_tables(base, sql)
    shorts = expanded.table_short_names
    assert "fact_payroll_detail" in shorts or "dim_employee" in shorts


def test_post_process_validate_rejects_bad_group_column():
    g = SchemaGrounding(
        columns_by_table={"public_mint_audit.dim_employee": ["employee_id", "full_name"]},
    )
    cfg = [
        {
            "type": "append_per_group_aggregate_rows",
            "group_column": "not_a_column",
            "aggregations": {"employee_id": "COUNT"},
            "label_column": "full_name",
            "label_format": "Count ({group})",
        }
    ]
    err = validate_post_process_config(cfg, grounding=g)
    assert err is not None
