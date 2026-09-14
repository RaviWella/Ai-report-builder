# Datamart SQL pipeline

## S3 chat orchestrator (`runner.py`)

`run_chat_pipeline` wires the stages below. Thin modules: `turn_setup`, `retrieval_gate`, `prompt_builder`, `execute_stage`, `add_scenario_runner`.

1. **schema_grounding** — S1 `schema_link_stage` (domain → broker → prune → link gate)
2. **retrieval_check** — legacy validation overlay; may block with clarification
3. **generate_sql** — S2 `sql_resolver` via `chat_engine.generate_sql_for_turn`
4. **validate_sql** — S2 `verify_sql` via `chat_engine.validate_sql_for_turn`
5. **execute_query** — warehouse SELECT + post-process (`execute_stage`)
6. Extra **ADDITIONAL_RESULT_BLOCKS** when applicable

Template modifications: `template_runner.py` (same verify step).

## Configuration

Use `settings.SETTINGS` or legacy `config.py` exports. Pipeline toggles:

| Env | Default |
|-----|---------|
| `DATAMART_BLOCK_INSUFFICIENT_RETRIEVAL` | true |
| `DATAMART_REQUIRE_SQL_ADEQUACY` | true |
| `DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN` | 1 |
| `DATAMART_BROKER_MAX_TABLES` | 8 |

## S6 — UI + persistence + live eval

- `pipeline_meta` stored in assistant `validation` JSON (see `datamart_chat._validation_to_json`)
- Frontend: **SQL pipeline** block in `DatamartValidationPanel`
- `run_question_bank_eval.py` prints `domain=` and `tier=` per question

## S5 — Respond + knowledge

- `PipelineTurnMeta` on API responses (`domain`, `sql_tier`, `sql_source`, `tables_linked`)
- `knowledge_registry.py` — unified bank + verified + template index
- `resolve_eval.py` + `tools/run_pipeline_eval.py` — offline link + Tier A/B resolve

```bash
PYTHONPATH=. python tools/run_pipeline_eval.py
pytest tests/datamart/test_s5_knowledge_and_resolve.py -q
```

## S4 — Question bank CI

Offline link eval (no LLM):

```bash
cd backend && PYTHONPATH=. python tools/run_link_eval.py
pytest tests/datamart/test_question_bank_link_ci.py -q
```

Checks: domain vs `eval_domain`, `expect_tables` vs domain allowlist, Tier-B domain guard.

## Extending verified examples

Add entries to `verified_queries.yaml` (see `tools/datamart_question_bank.yaml` for prompts).
Run `pytest tests/datamart/test_verified_query_store.py`.
