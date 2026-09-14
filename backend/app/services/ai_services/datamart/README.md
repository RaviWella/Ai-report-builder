# Datamart AI agent

## Layout

| Path | Purpose |
|------|---------|
| `agent.py`, `chat_pipeline.py` | Public entry points |
| `models.py`, `config.py`, `settings.py` | Shared models and settings |
| `schema.py`, `schema_broker.py` | Warehouse introspection and grounding |
| `pipeline/` | Chat pipeline stages and `runner.py` orchestrator |
| `sql/` | SQL generation, binding, execution, recovery |
| `llm/` | LLM client and response parsing |
| `prompts/` | Prompts and context assembly |
| `scenario/` | Add-scenario and extra result blocks |
| `semantic/` | Catalog, DataHub, join hints |
| `domain_sql/` | Domain SQL templates (Tier A) |
| `validation/` | Validation and trust |
| `postprocess/` | Post-process transforms |
| `workspace/` | Sessions, templates, tenant runtime |
| `orchestration/` | Modify mode, clarification, template pipeline |
