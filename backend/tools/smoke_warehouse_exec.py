"""Smoke-test warehouse execute for payroll summary SQL."""
from app.services.ai_services.datamart.pipeline.verified_query_store import (
    clear_verified_query_cache,
    materialize_sql,
    retrieve_verified_sql,
)
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.schema import execute_sql
from app.services.ai_services.datamart.schema_broker import (
    build_schema_grounding,
    BrokerMode,
    expand_grounding_with_tables,
)


def _run() -> None:
    clear_verified_query_cache()
    q = (
        "Prepare a payroll summary report with employee name, employee ID, "
        "payroll group name, pay frequency, currency code, branch, and "
        "current basic salary for active employees only."
    )
    g = build_schema_grounding(question=q, mode=BrokerMode.CHAT)
    hit = retrieve_verified_sql(q, grounded_tables=set(g.table_short_names), domain="payroll")
    if not hit:
        print("no verified sql")
        return
    sql, src, _ = hit
    print("source:", src)
    g2 = expand_grounding_with_tables(g, sql)
    cols, rows, count = execute_sql(sql, g2)
    print("ok cols=", cols[:6], "rows=", count)


if __name__ == "__main__":
    run_with_datamart_context("demo_tenant", _run)
