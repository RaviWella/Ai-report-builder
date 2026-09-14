# Datamart pipeline (v1.5)

Industry-style **link → resolve → verify → execute** flow. Implementation lives under `pipeline/`.

## Stages

| Stage | Module | Trace step |
|-------|--------|------------|
| Intent + domain | `turn_setup`, `domain_classifier` | (embedded in schema_grounding) |
| Schema link (S1) | `schema_link_stage` | `schema_grounding` |
| Retrieval overlay | `retrieval_gate` | `retrieval_check` |
| SQL resolve (S2) | `sql_resolver` | `generate_sql` |
| Verify (S2) | `verify_sql` | `validate_sql` |
| Execute | `execute_stage` | `execute_query` |

Tier **A** = catalog templates · **B** = `verified_queries.yaml` · **C** = plan-then-SQL (LLM).

## Configuration

Prefer `settings.SETTINGS`. Key env vars:

```env
DATAMART_PROFILE=tenant_etl
DATAMART_LEGACY_FALLBACK=false
DATAMART_BLOCK_INSUFFICIENT_RETRIEVAL=true
DATAMART_REQUIRE_SQL_ADEQUACY=true
DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN=1
DATAMART_BROKER_MAX_TABLES=8
```

## Eval & CI (S4)

| Tool / test | Purpose |
|-------------|---------|
| `tools/run_link_eval.py` | Offline: domain + allowlist + Tier-B guard (no LLM/warehouse) |
| `tools/run_datamart_eval.py` | Golden ReportSpec SQL + broker (live or mocked) |
| `tools/run_question_bank_eval.py` | Live broker per bank set (slow) |
| `tests/datamart/test_question_bank_link_ci.py` | CI for link eval |
| `tests/datamart/test_question_bank_catalog_ci.py` | CI for template SQL |
| `tests/datamart/test_datamart_eval_ci.py` | CI for golden reports |

Question bank: `tools/datamart_question_bank.yaml` (66 prompts, 11×6 sets).

Verified SQL seeds: `verified_queries.yaml` — add domain-tagged pairs as eval passes.

## Extending

1. Add `eval_domain` + `expect_tables` rows to the question bank.
2. Run `PYTHONPATH=. python tools/run_link_eval.py`.
3. Add matching `verified_queries.yaml` entries for Tier B.
4. Run `pytest tests/datamart/test_question_bank_link_ci.py`.

See also `pipeline/README.md` for module-level notes.

## S5 — Respond + knowledge registry

| Piece | Role |
|-------|------|
| `PipelineTurnMeta` on `DatamartResponse` | `domain`, `sql_tier` (A/B/C), `sql_source`, `tables_linked` |
| `pipeline/knowledge_registry.py` | Loads question bank + verified queries + template ids |
| `pipeline/resolve_eval.py` | Offline Tier A/B probe per bank row (mock grounding) |
| `tools/run_pipeline_eval.py` | Link + resolve combined report |

```bash
cd backend && PYTHONPATH=. python tools/run_pipeline_eval.py
pytest tests/datamart/test_s5_knowledge_and_resolve.py -q
```

API responses now include `pipeline_meta` alongside `pipeline_trace` for UI or debugging.

## S6 — UI, persistence, live eval

| Piece | Role |
|-------|------|
| `_validation_to_json` | Persists `pipeline_meta` in assistant `validation` JSON (with `pipeline_trace`) |
| `DatamartValidationPanel` | Shows domain, tier, source, linked tables |
| Session reload | `DatamartChat` restores `pipeline_meta` / `pipeline_trace` from stored validation |
| `pipeline/question_bank_report.py` | Live `run_question_bank_eval.py` logs `classified_domain` + `sql_tier` per row |

```bash
PYTHONPATH=. python tools/run_question_bank_eval.py --set 10
```

`retrieval_relevance.py` is deprecated (S1 linker replaced it); kept for unit tests only.
