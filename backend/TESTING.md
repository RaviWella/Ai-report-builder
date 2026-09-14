# Datamart local testing & production checklist

## One command (Windows)

From repo root:

```powershell
.\scripts\run_local_datamart_setup.ps1
```

## Manual steps (all platforms)

From `backend/` with `PYTHONPATH=.`:

```bash
# 1. Offline pipeline eval (no LLM / warehouse)
python tools/run_pipeline_eval.py
python tools/run_link_eval.py

# 2. CI tests
pytest tests/datamart/test_question_bank_link_ci.py \
  tests/datamart/test_s5_knowledge_and_resolve.py \
  tests/datamart/test_s6_pipeline_meta.py \
  tests/datamart/test_datamart_eval_ci.py -q

# 3. Warehouse + catalog (requires DB access)
python tools/semantic_catalog_tool.py refresh --tenant demo_tenant --write
python tools/seed_demo_tenant_registry_warehouse.py

# 4. Optional live broker eval (slow)
python tools/run_question_bank_eval.py --set 10
```

## Environment (`.env`)

Production-oriented datamart flags:

```env
DATAMART_PROFILE=tenant_etl
DATAMART_LEGACY_FALLBACK=false
DATAMART_BLOCK_INSUFFICIENT_RETRIEVAL=true
DATAMART_REQUIRE_SQL_ADEQUACY=true
DATAMART_CHAT_CLARIFICATION_UI=true
DATAMART_MAX_REPAIR_ATTEMPTS_PER_TURN=1
DATAMART_BROKER_MAX_TABLES=8
```

## Run app

```bash
# Terminal 1
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd frontend && npm run dev
```

## UI

Chat shows a **staged pipeline loader** (progress bar + steps) while the API runs, then a short **Answer ready** state before the report appears. After the reply, open **How this answer was built** and **Sources & validation → SQL pipeline** for domain, tier, and source.

See [`app/services/ai_services/datamart/PIPELINE.md`](app/services/ai_services/datamart/PIPELINE.md) for architecture.
