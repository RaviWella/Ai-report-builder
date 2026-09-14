import time
from app.services.ai_services.datamart.orchestration.intent_router import classify_chat_intent
from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.pipeline.schema_link_stage import SchemaLinkInput, link_schema_for_turn
from app.services.ai_services.datamart.domain_sql.report_spec import compile_report_spec
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context


def _run():
    _, cases = load_question_bank()
    q = cases[0]["question"]
    t0 = time.perf_counter()
    print("context ok", flush=True)
    intent = classify_chat_intent(q, last_sql=None, has_prior_post_process=False)
    print(f"intent {time.perf_counter()-t0:.1f}s", flush=True)
    spec = compile_report_spec(q, chat_intent=intent)
    print(f"spec {time.perf_counter()-t0:.1f}s", flush=True)
    link = link_schema_for_turn(SchemaLinkInput(question=q, chat_intent=intent, broker_last_sql=None, confirmed_table_names=None, report_spec=spec))
    print(f"link {time.perf_counter()-t0:.1f}s tables={link.grounding.table_short_names[:6]}", flush=True)


run_with_datamart_context("demo_tenant", _run)
