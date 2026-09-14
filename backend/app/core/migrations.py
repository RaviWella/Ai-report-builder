"""Run application-database Alembic migrations (hrm_platform / hrm_control)."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.application_db import application_sync_url
from app.core.config import settings

logger = logging.getLogger("migrations")

# Postgres advisory lock — serializes migrations when multiple API replicas start together.
_MIGRATION_LOCK_ID = 0x4D48524D  # "MHRM"
_DEFAULT_LOCK_TIMEOUT_SEC = 45


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    ini_path = backend_root / "alembic.ini"
    if not ini_path.is_file():
        raise FileNotFoundError(f"alembic.ini not found at {ini_path}")
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


def _acquire_migration_lock(conn, timeout_sec: int) -> None:
    """Try advisory lock with timeout (avoids infinite hang on --reload / stale sessions)."""
    deadline = time.monotonic() + timeout_sec
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": _MIGRATION_LOCK_ID},
        ).scalar()
        if acquired:
            if attempt > 1:
                logger.info("Migration advisory lock acquired after %d attempts", attempt)
            return
        if attempt == 1:
            logger.warning(
                "Another process holds the migration lock — waiting up to %ds "
                "(stop duplicate uvicorn instances or use RUN_MIGRATIONS_ON_STARTUP=false)",
                timeout_sec,
            )
        time.sleep(0.5)
    raise TimeoutError(
        f"Could not acquire migration advisory lock within {timeout_sec}s. "
        "Another API instance or a stuck Postgres session may be running migrations. "
        "Stop other uvicorn processes, or set RUN_MIGRATIONS_ON_STARTUP=false and run "
        "'alembic upgrade head' once manually."
    )


def run_platform_migrations() -> None:
    """Apply ``alembic upgrade head`` on the application database (FastAPI lifespan only).

    Docker deployments migrate in ``docker-entrypoint.sh`` instead; entrypoint sets
    ``RUN_MIGRATIONS_ON_STARTUP=false`` before uvicorn to avoid running twice.

    No-op when ``RUN_MIGRATIONS_ON_STARTUP`` is false.
    Uses a Postgres advisory lock so only one replica runs migrations at a time.
    Revisions must be idempotent (IF NOT EXISTS / column-exists checks).
    """
    if not settings.RUN_MIGRATIONS_ON_STARTUP:
        logger.info("RUN_MIGRATIONS_ON_STARTUP=false — skipping Alembic")
        return

    timeout_sec = int(
        getattr(settings, "MIGRATION_LOCK_TIMEOUT_SEC", _DEFAULT_LOCK_TIMEOUT_SEC)
        or _DEFAULT_LOCK_TIMEOUT_SEC
    )
    cfg = _alembic_config()
    engine = create_engine(application_sync_url(), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET lock_timeout = '15s'"))
            _acquire_migration_lock(conn, timeout_sec)
            conn.commit()
            try:
                logger.info("Running alembic upgrade head on application database…")
                command.upgrade(cfg, "head")
                logger.info("Alembic upgrade head complete")
            finally:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": _MIGRATION_LOCK_ID},
                )
                conn.commit()
    finally:
        engine.dispose()
