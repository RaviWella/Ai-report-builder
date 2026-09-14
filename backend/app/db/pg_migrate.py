"""Optional startup auto-migrate for PostgreSQL."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def run_pg_migrations_if_enabled() -> None:
    if not settings.pg_auto_migrate:
        return
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini = backend_root / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("pg_auto_migrate skipped: alembic.ini not found at %s", alembic_ini)
        return
    logger.info("Running PostgreSQL migrations (PG_AUTO_MIGRATE=true)")
    subprocess.run(
        ["alembic", "-c", str(alembic_ini), "upgrade", "head"],
        cwd=backend_root,
        check=True,
    )
