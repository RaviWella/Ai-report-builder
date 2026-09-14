#!/usr/bin/env python3
"""Create database_connections / data_access_rules in tenant warehouse mart schema."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.mart_metadata import ensure_mart_metadata_tables_sync
from app.core.warehouse import connection_params, get_layout_sync, get_warehouse_engine_sync

tenant_id = sys.argv[1] if len(sys.argv) > 1 else "demo_tenant"
layout = get_layout_sync(tenant_id)
params = connection_params(tenant_id)
engine = get_warehouse_engine_sync(tenant_id)
created = ensure_mart_metadata_tables_sync(engine, layout.mart_schema)
print(f"tenant={tenant_id} mart={layout.mart_schema} created={created} db={params['database']}")
