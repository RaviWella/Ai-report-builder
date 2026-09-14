#!/usr/bin/env python3
"""
Generate a DataHub Postgres ingest recipe for a tenant ETL warehouse (hr_semantic, hr, hr_snap).

Usage (from backend/):
  python tools/generate_tenant_datahub_ingest.py --tenant-id demo_tenant
  python tools/generate_tenant_datahub_ingest.py --tenant-id demo_tenant --write ../datahub_ingestion.generated.yml

Reads connection from DATAMART_DB_* or tenant_registry via warehouse.connection_params.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ai_services.datamart import config as dm_config  # noqa: E402
from app.services.ai_services.datamart.workspace.runtime_context import (  # noqa: E402
    DatamartProfile,
    resolve_datamart_context,
)


def _schemas_yaml_block(schemas: tuple[str, ...]) -> str:
    lines = "\n".join(f'        - "{s}"' for s in schemas)
    return f"    schema_pattern:\n      allow:\n{lines}\n"


def build_recipe_yaml(*, tenant_id: str) -> str:
    ctx = resolve_datamart_context(tenant_id)
    if ctx.profile != DatamartProfile.TENANT_ETL:
        raise SystemExit(
            f"Tenant {tenant_id!r} resolved to profile={ctx.profile.value}. "
            "Set DATAMART_PROFILE=tenant_etl and DATAMART_DB_NAME=hrm_wh_* in .env."
        )

    from app.core.warehouse import connection_params

    params = connection_params(tenant_id)
    host = params["host"]
    port = params["port"]
    database = params["database"]
    user = params["user"]
    password = params["password"]

    gms = (dm_config.DATAHUB_GMS_URL or "http://localhost:8080").strip()
    token = (dm_config.DATAHUB_GMS_TOKEN or "").strip()
    token_line = f'    token: "{token}"\n' if token else ""

    schemas = ctx.query_schemas
    return (
        f"# Generated for tenant={tenant_id} profile=tenant_etl — do not commit\n"
        f"source:\n"
        f"  type: postgres\n"
        f"  config:\n"
        f'    host_port: "{host}:{port}"\n'
        f'    database: "{database}"\n'
        f'    username: "{user}"\n'
        f'    password: "{password}"\n'
        f"{_schemas_yaml_block(schemas)}"
        f"sink:\n"
        f"  type: datahub-rest\n"
        f"  config:\n"
        f'    server: "{gms}"\n'
        f"{token_line}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tenant ETL DataHub ingest YAML")
    parser.add_argument("--tenant-id", default=dm_config.DATAMART_DEFAULT_TENANT_ID)
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Output path (default: print to stdout)",
    )
    args = parser.parse_args()
    yaml_text = build_recipe_yaml(tenant_id=args.tenant_id.strip())
    if args.write:
        args.write.write_text(yaml_text, encoding="utf-8")
        print(f"Wrote {args.write} for tenant={args.tenant_id}")
    else:
        print(yaml_text)


if __name__ == "__main__":
    main()
