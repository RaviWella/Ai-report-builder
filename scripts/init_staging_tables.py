"""Create warehouse layers + staging tables for a tenant.

Usage:
  cd backend && python ../scripts/init_staging_tables.py
  cd backend && python ../scripts/init_staging_tables.py --tenant-id demo_tenant
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.warehouse import (  # noqa: E402
    ensure_warehouse_ready_sync,
    get_layout_sync,
    get_warehouse_engine_sync,
)


def main(tenant_id: str) -> None:
    layout = get_layout_sync(tenant_id)
    wh = get_warehouse_engine_sync(tenant_id)
    try:
        ensure_warehouse_ready_sync(wh, tenant_id)
    finally:
        wh.dispose()

    print(
        f"Ensured warehouse layers + staging in schema {layout.raw_schema}"
        f" (database={layout.database_name or 'platform'})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", default="demo_tenant")
    main(parser.parse_args().tenant_id)
