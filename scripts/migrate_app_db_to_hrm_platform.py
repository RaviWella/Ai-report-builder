#!/usr/bin/env python3
"""Migrate MintHRM control-plane data from the legacy ``postgres`` DB to ``hrm_platform``.

Copies schema ``hrm_control`` (tenant_registry, tenant_etl_sources, …) and optional
``public.alembic_version`` so Alembic state is preserved.

Usage (from repo root):

  python scripts/migrate_app_db_to_hrm_platform.py
  python scripts/migrate_app_db_to_hrm_platform.py --dry-run
  python scripts/migrate_app_db_to_hrm_platform.py --source-db postgres --target-db hrm_platform
  python scripts/migrate_app_db_to_hrm_platform.py --replace

Requires backend/.env with Postgres credentials (DATABASE_URL or APPLICATION_DATABASE_URL).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.application_db import (  # noqa: E402
    build_url,
    connection_parts,
    get_postgres_admin_engine_sync,
    with_database,
)
from app.core.config import settings  # noqa: E402

CONTROL_SCHEMA = "hrm_control"
TABLE_ORDER = ("tenant_registry", "tenant_etl_sources")


def _engine_for_db(database: str) -> Engine:
    parts = connection_parts(settings.application_database_url)
    url = build_url(
        host=parts["host"],
        port=int(parts["port"]),
        user=parts["user"],
        password=parts["password"],
        database=database,
        driver="psycopg2",
    )
    return create_engine(url, pool_pre_ping=True)


def _ensure_database_exists(database: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] Would create database {database!r} if missing")
        return
    admin = get_postgres_admin_engine_sync()
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db"),
                {"db": database},
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{database}"'))
                print(f"Created database {database!r}")
            else:
                print(f"Database {database!r} already exists")
    finally:
        admin.dispose()
    eng = _engine_for_db(database)
    try:
        with eng.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{CONTROL_SCHEMA}"'))
    finally:
        eng.dispose()


def _list_control_tables(engine: Engine) -> list[str]:
    insp = inspect(engine)
    tables = [t for t in insp.get_table_names(schema=CONTROL_SCHEMA) if not t.startswith("alembic")]
    ordered = [t for t in TABLE_ORDER if t in tables]
    rest = sorted(t for t in tables if t not in ordered)
    return ordered + rest


def _primary_key_columns(engine: Engine, table: str) -> list[str]:
    insp = inspect(engine)
    pk = insp.get_pk_constraint(table, schema=CONTROL_SCHEMA)
    return list(pk.get("constrained_columns") or [])


def _row_count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text(f'SELECT COUNT(*) FROM "{CONTROL_SCHEMA}"."{table}"')
        ).scalar_one()


def _copy_table(
    source: Engine,
    target: Engine,
    table: str,
    *,
    dry_run: bool,
    replace: bool,
) -> int:
    qualified = f'"{CONTROL_SCHEMA}"."{table}"'
    n_src = _row_count(source, table)

    if dry_run:
        print(f"  [dry-run] Would copy {n_src} rows -> {qualified}")
        return n_src

    with source.connect() as src_conn, target.connect() as tgt_conn:
        if replace and n_src >= 0:
            tgt_conn.execute(text(f"TRUNCATE TABLE {qualified} RESTART IDENTITY CASCADE"))
            tgt_conn.commit()

        if n_src == 0:
            print(f"  {table}: 0 rows (skip)")
            return 0

        rows = src_conn.execute(text(f"SELECT * FROM {qualified}")).mappings().all()
        if not rows:
            print(f"  {table}: 0 rows")
            return 0

        cols = list(rows[0].keys())
        col_list = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        insert_sql = text(
            f"INSERT INTO {qualified} ({col_list}) VALUES ({placeholders})"
        )

        pk_cols = _primary_key_columns(target, table)
        if pk_cols:
            conflict = ", ".join(f'"{c}"' for c in pk_cols)
            insert_sql = text(
                f"INSERT INTO {qualified} ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict}) DO NOTHING"
            )

        for row in rows:
            tgt_conn.execute(insert_sql, dict(row))
        tgt_conn.commit()
        copied = len(rows)

        # Sync serial sequences
        for col in cols:
            if col == "id" or col.endswith("_id"):
                try:
                    tgt_conn.execute(
                        text(
                            f"""
                            SELECT setval(
                                pg_get_serial_sequence('{CONTROL_SCHEMA}.{table}', '{col}'),
                                COALESCE((SELECT MAX("{col}") FROM {qualified}), 1)
                            )
                            """
                        )
                    )
                except Exception:
                    pass
        tgt_conn.commit()

    print(f"  {table}: copied {len(rows)} row(s) from source")
    return len(rows)


def _copy_alembic_version(source: Engine, target: Engine, *, dry_run: bool) -> None:
    with source.connect() as conn:
        if not inspect(source).has_table("alembic_version", schema="public"):
            print("  alembic_version: not on source (skip)")
            return
        row = conn.execute(text("SELECT version_num FROM public.alembic_version")).first()
        if not row:
            print("  alembic_version: empty on source (skip)")
            return
        version = row[0]

    if dry_run:
        print(f"  [dry-run] Would set public.alembic_version = {version!r}")
        return

    with target.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS public.alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("DELETE FROM public.alembic_version"))
        conn.execute(
            text("INSERT INTO public.alembic_version (version_num) VALUES (:v)"),
            {"v": version},
        )
        conn.commit()
    print(f"  alembic_version: set to {version!r}")


def _run_alembic_on_target(target_db: str) -> None:
    """Ensure target has full schema (safe if already migrated)."""
    url = with_database(
        settings.application_database_url,
        target_db,
        driver=None,
    ).replace("postgresql://", "postgresql+psycopg2://", 1)
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")

    env = {**dict(**__import__("os").environ), "DATABASE_URL": url}
    print("Running alembic upgrade head on target…")
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy hrm_control from legacy postgres DB to hrm_platform application DB."
    )
    parser.add_argument(
        "--source-db",
        default="postgres",
        help="Source database name (default: postgres)",
    )
    parser.add_argument(
        "--target-db",
        default=None,
        help=f"Target database name (default: {settings.APP_DATABASE_NAME})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="TRUNCATE target tables before copy",
    )
    parser.add_argument(
        "--skip-alembic",
        action="store_true",
        help="Do not run alembic upgrade on target (you already migrated schema)",
    )
    args = parser.parse_args()

    target_db = (args.target_db or settings.APP_DATABASE_NAME or "hrm_platform").strip()
    source_db = args.source_db.strip()

    if source_db == target_db:
        print(f"Source and target are both {source_db!r}; nothing to do.")
        return 0

    print(f"MintHRM app DB migration: {source_db!r} -> {target_db!r}")
    print(f"Host: {connection_parts(settings.application_database_url)['host']}")

    if not args.dry_run:
        _ensure_database_exists(target_db, dry_run=False)

        if not args.skip_alembic:
            try:
                _run_alembic_on_target(target_db)
            except FileNotFoundError:
                print(
                    "Warning: alembic not on PATH — run manually:\n"
                    f"  cd backend && set DATABASE_URL=postgresql://...@.../{target_db} && alembic upgrade head"
                )
            except subprocess.CalledProcessError as exc:
                print(f"alembic failed (exit {exc.returncode}); continuing with data copy…")

    source_eng = _engine_for_db(source_db)
    target_eng = _engine_for_db(target_db)

    try:
        with source_eng.connect() as conn:
            has_schema = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"
                ),
                {"s": CONTROL_SCHEMA},
            ).first()
        if not has_schema:
            print(f"No {CONTROL_SCHEMA} schema on source DB {source_db!r}. Nothing to migrate.")
            return 0

        tables = _list_control_tables(source_eng)
        if not tables:
            print(f"{CONTROL_SCHEMA} exists but has no tables on source.")
            return 0

        print(f"Tables to copy: {', '.join(tables)}")
        total = 0
        for table in tables:
            total += _copy_table(
                source_eng,
                target_eng,
                table,
                dry_run=args.dry_run,
                replace=args.replace,
            )

        print("Alembic version stamp:")
        _copy_alembic_version(source_eng, target_eng, dry_run=args.dry_run)

        if args.dry_run:
            print("\nDry run complete. Re-run without --dry-run to apply.")
        else:
            print(
                f"\nDone. Update backend/.env:\n"
                f"  DATABASE_URL=.../{target_db}\n"
                f"  APP_DATABASE_NAME={target_db}\n"
                f"Then restart the API."
            )
        return 0
    finally:
        source_eng.dispose()
        target_eng.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
