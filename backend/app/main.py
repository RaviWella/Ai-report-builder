"""MintHRM Intelligence Platform — FastAPI entry point."""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db_sync
from app.core.logging_setup import configure_logging
from app.core.migrations import run_platform_migrations
from app.core.request_logging import RequestLoggingMiddleware
from app.health import check_application_health
from app.api.routes import api_router
import app.models  # noqa: F401 — registers SQLAlchemy models with Base

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)
configure_logging(debug=settings.DEBUG)
logger = logging.getLogger("app")


def _bootstrap_datamart_llm_env() -> None:
    """Run on import so `python -m uvicorn app.main:app` works without run-dev.ps1.

    Clears a stale Windows OPENAI_API_KEY that would break datamart (LiteLLM 401).
    """
    try:
        from app.services.ai_services.datamart.llm.llm_client import (
            clear_llm_cache,
            sync_process_openai_api_key,
        )
        from app.services.ai_services.datamart.llm.llm_settings import log_llm_config_status

        clear_llm_cache()
        sync_process_openai_api_key()
        log_llm_config_status()
    except Exception as exc:
        logger.warning("Datamart LLM bootstrap skipped: %s", exc)


_bootstrap_datamart_llm_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup — Alembic on application DB (local uvicorn only; Docker uses entrypoint), then init_db
    logger.info("Application startup: initializing database…")
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        try:
            run_platform_migrations()
        except TimeoutError:
            logger.error(
                "Migration lock timeout — stop duplicate uvicorn processes or set "
                "RUN_MIGRATIONS_ON_STARTUP=false in backend/.env"
            )
            if settings.MIGRATION_FAIL_FAST:
                raise
        except Exception:
            if settings.MIGRATION_FAIL_FAST:
                raise
            logger.exception(
                "Alembic upgrade failed (MIGRATION_FAIL_FAST=false — starting anyway)"
            )
    else:
        logger.info(
            "RUN_MIGRATIONS_ON_STARTUP=false — skipping lifespan Alembic "
            "(Docker entrypoint already migrated or migrations disabled)"
        )
    try:
        await asyncio.to_thread(init_db_sync)
        logger.info("Application database ready")
    except Exception as exc:
        if settings.MIGRATION_FAIL_FAST:
            raise
        logger.warning("Database init failed (app will start anyway): %s", exc)

    _bootstrap_datamart_llm_env()

    if not settings.DB_ENCRYPTION_KEY:
        logger.warning(
            "DB_ENCRYPTION_KEY is not set — database connection CRUD will fail. "
            'Generate: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )

    from app.services.ai_services.datamart.llm.llm_settings import resolve_llm_connection

    try:
        conn = resolve_llm_connection("gpt-oss:20b")
        logger.info(
            "Application startup complete — API ready on port (see uvicorn). "
            "Datamart LLM: backend=%s model=%s base=%s",
            conn.backend,
            conn.model,
            conn.base_url,
        )
    except Exception as exc:
        logger.warning("Application startup complete (datamart LLM not ready: %s)", exc)

    _warn_duplicate_port_8000_listeners()

    yield
    # Shutdown — nothing to clean up yet


def _warn_duplicate_port_8000_listeners() -> None:
    """Windows: an old python.exe on 127.0.0.1:8000 steals localhost traffic from uvicorn."""
    if sys.platform != "win32":
        return
    try:
        import subprocess

        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            errors="ignore",
            timeout=5,
        )
    except Exception:
        return
    listeners: list[tuple[str, str]] = []
    for line in out.splitlines():
        if ":8000" not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) >= 5:
            listeners.append((parts[1], parts[-1]))
    if len(listeners) > 1:
        logger.warning(
            "Multiple processes are listening on port 8000: %s. "
            "Stop old python.exe PIDs (Task Manager or: Stop-Process -Id <pid>) "
            "or localhost may hit a stale API without datamart LLM fixes.",
            ", ".join(f"{addr} pid={pid}" for addr, pid in listeners),
        )


app = FastAPI(
    title=settings.APP_NAME,
    description="MintHRM Intelligence Platform API — HR analytics on top of MintHRM MySQL source.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
@app.get("/ready")
def health_check():
    """Liveness + readiness: DB reachable and Alembic revision present."""
    payload = check_application_health()
    status_code = 200 if payload["status"] == "healthy" else 503
    return JSONResponse(content=payload, status_code=status_code)
