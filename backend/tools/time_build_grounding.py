import time
from app.services.ai_services.datamart.orchestration.intent_router import ChatIntent
from app.services.ai_services.datamart.pipeline.link_eval import load_question_bank
from app.services.ai_services.datamart.domain_sql.report_spec import compile_report_spec
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.schema_broker import BrokerMode, build_schema_grounding
from app.services.ai_services.datamart.semantic.semantic_layer import resolve_semantics
from app.services.ai_services.datamart.pipeline.schema_link_stage import _catalog_must_include_tables, _report_spec_domain
from app.services.ai_services.datamart.pipeline.domain_classifier import classify_domain


def _run():
    _, cases = load_question_bank()
    q = cases[0]["question"]
    t0 = time.perf_counter()
    semantics = resolve_semantics(q)
    print(f"semantics {time.perf_counter()-t0:.1f}s seeds={semantics.seed_tables[:4]}", flush=True)
    classified = classify_domain(q, topics_matched=semantics.topics_matched)
    spec = compile_report_spec(q)
    domain = _report_spec_domain(spec) or classified.domain
    must = _catalog_must_include_tables(q, domain=domain, semantics=semantics, report_spec=spec, confirmed=None)
    print(f"must_include {time.perf_counter()-t0:.1f}s n={len(must)} {must[:8]}", flush=True)
    g = build_schema_grounding(question=q, mode=BrokerMode.CHAT, seed_table_names=must or None, chat_intent=ChatIntent.NEW_QUERY)
    print(f"grounding {time.perf_counter()-t0:.1f}s tables={g.table_short_names}", flush=True)


run_with_datamart_context("demo_tenant", _run)
