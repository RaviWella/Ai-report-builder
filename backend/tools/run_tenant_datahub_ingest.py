#!/usr/bin/env python
"""
Phase 6b — generate tenant DataHub ingest recipe and run datahub ingest.

Usage (from backend/):
  python tools/run_tenant_datahub_ingest.py --tenant-id demo_tenant
  python tools/run_tenant_datahub_ingest.py --tenant-id demo_tenant --dry-run

Requires DataHub CLI: pip install acryl-datahub acryl-datahub[postgres]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_BACKEND / ".env")


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Tenant ETL DataHub ingest (Phase 6b)")
    parser.add_argument("--tenant-id", default=os.getenv("DATAMART_DEFAULT_TENANT_ID", "demo_tenant"))
    parser.add_argument(
        "--output",
        type=Path,
        default=_BACKEND.parent / "datahub_ingestion.generated.yml",
        help="Generated recipe path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only generate recipe YAML, do not run datahub ingest",
    )
    args = parser.parse_args(argv)

    from tools.generate_tenant_datahub_ingest import build_recipe_yaml

    tenant = args.tenant_id.strip()
    yaml_text = build_recipe_yaml(tenant_id=tenant)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml_text, encoding="utf-8")
    print(f"Wrote recipe {args.output} for tenant={tenant}")

    if args.dry_run:
        return 0

    datahub = shutil.which("datahub")
    if not datahub:
        print(
            "datahub CLI not found. Install: pip install acryl-datahub acryl-datahub[postgres]",
            file=sys.stderr,
        )
        return 2

    print(f"Running: datahub ingest -c {args.output}")
    proc = subprocess.run(
        [datahub, "ingest", "-c", str(args.output)],
        cwd=str(_BACKEND.parent),
    )
    return int(proc.returncode or 0)


if __name__ == "__main__":
    sys.exit(main())
