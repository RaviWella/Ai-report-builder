"""
Introspect tenant warehouse tables/columns for datamart planning (read-only).

Usage (from backend/):
  PYTHONPATH=. python tools/probe_warehouse_schema.py
  PYTHONPATH=. python tools/probe_warehouse_schema.py --domain payroll
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app.services.ai_services.datamart import config as dm_config
from app.services.ai_services.datamart.workspace.runtime_context import run_with_datamart_context
from app.services.ai_services.datamart.schema import introspect_table_columns, list_warehouse_tables


def _probe(domain: str, limit: int) -> dict:
    all_tables = list_warehouse_tables()
    if domain:
        filt = domain.lower()
        selected = [t for t in all_tables if filt in t.lower()][:limit]
    else:
        selected = all_tables[:limit]
    col_map = introspect_table_columns(selected)
    return {
        "schemas": list(dm_config.parse_query_schemas()),
        "table_count": len(all_tables),
        "tables_sample": all_tables[:50],
        "introspected": col_map,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default=dm_config.DATAMART_DEFAULT_TENANT_ID)
    parser.add_argument("--domain", default="", help="Filter table names containing token")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    payload = run_with_datamart_context(
        args.tenant,
        _probe,
        args.domain,
        args.limit,
    )
    print(json.dumps({"tenant": args.tenant, **payload}, indent=2, default=str))


if __name__ == "__main__":
    main()
