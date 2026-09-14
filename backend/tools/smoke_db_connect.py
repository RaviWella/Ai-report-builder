import time
from sqlalchemy import text
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context, require_datamart_context

def _run():
    ctx = require_datamart_context()
    print("db", ctx.database_name, flush=True)
    t0 = time.perf_counter()
    with ctx.engine.connect() as conn:
        print("connected", time.perf_counter()-t0, flush=True)
        r = conn.execute(text("SELECT 1")).scalar()
        print("select", r, time.perf_counter()-t0, flush=True)

run_with_datamart_context("demo_tenant", _run)
