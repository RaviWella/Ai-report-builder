"""Time each step of Q1 eval to find hang."""
import time

from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.pipeline.question_bank_full_sql_eval import evaluate_full_sql_one
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context


def _run() -> None:
    _, cases = load_question_bank()
    case = cases[0]
    t0 = time.perf_counter()
    print("start evaluate_full_sql_one", flush=True)
    r = evaluate_full_sql_one(case, index=0, mode="live", execute=True)
    print(f"done in {time.perf_counter()-t0:.1f}s ok={r.ok}", flush=True)
    if r.errors:
        print("errors:", r.errors[:3], flush=True)
    if r.result_columns:
        print("cols:", r.result_columns[:8], flush=True)


if __name__ == "__main__":
    run_with_datamart_context("demo_tenant", _run)
