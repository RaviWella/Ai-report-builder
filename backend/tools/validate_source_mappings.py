"""Validate minthrm_* YAML column mappings against a live MySQL source database.

Usage (from backend/):
  python tools/validate_source_mappings.py
  python tools/validate_source_mappings.py --profile minthrm --variant mysql

Exits 0 when all mapped columns exist; exits 1 and prints mismatches otherwise.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MAPPINGS_DIR = BACKEND_ROOT / "app" / "services" / "hr_etl" / "mappings"


def _mysql_url_from_env() -> str:
    cfg = dotenv_values(BACKEND_ROOT / ".env")
    host = cfg.get("MYSQL_HOST", "localhost")
    port = cfg.get("MYSQL_PORT", "3306")
    db = cfg.get("MYSQL_DB", "")
    user = cfg.get("MYSQL_USER", "")
    pwd = cfg.get("MYSQL_PASSWORD", "")
    if not all([db, user, pwd]):
        raise SystemExit("MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD required in backend/.env")
    from urllib.parse import quote_plus

    return f"mysql+pymysql://{quote_plus(user or '')}:{quote_plus(pwd or '')}@{host}:{port}/{db}"


def _table_columns(engine, table_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).fetchall()
    return {str(r[0]).lower() for r in rows}


def validate_mapping(profile: str, variant: str, engine) -> list[str]:
    path = MAPPINGS_DIR / f"{profile}_{variant}.yaml"
    if not path.is_file():
        return [f"Mapping file not found: {path}"]

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tables: dict[str, str] = dict(data.get("tables") or {})
    columns: dict[str, dict[str, str]] = {
        k: dict(v) for k, v in (data.get("columns") or {}).items()
    }

    issues: list[str] = []
    for table_key, col_map in sorted(columns.items()):
        physical_table = tables.get(table_key)
        if not physical_table:
            issues.append(f"{table_key}: missing entry under tables:")
            continue
        try:
            physical_cols = _table_columns(engine, physical_table)
        except Exception as exc:
            issues.append(f"{table_key} (`{physical_table}`): table error — {exc}")
            continue
        if not physical_cols:
            issues.append(f"{table_key} (`{physical_table}`): no columns returned")
            continue
        for logical, physical in sorted(col_map.items()):
            if physical.lower() not in physical_cols:
                issues.append(
                    f"{table_key} (`{physical_table}`): "
                    f"logical '{logical}' → physical '{physical}' NOT FOUND"
                )
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="minthrm")
    parser.add_argument("--variant", default="mysql")
    args = parser.parse_args()

    engine = create_engine(_mysql_url_from_env())
    issues = validate_mapping(args.profile, args.variant, engine)
    if issues:
        print(f"FAILED: {len(issues)} mapping issue(s) for {args.profile}_{args.variant}")
        for line in issues:
            print(f"  - {line}")
        sys.exit(1)
    print(f"OK: all mapped columns exist for {args.profile}_{args.variant}")


if __name__ == "__main__":
    main()
