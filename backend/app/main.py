"""FastAPI entrypoint (Architecture §4.1/§4.2).

Wires the v1 routers, structured logging, a per-request request_id, and a health
check. Auth/RBAC/tenant scoping live as per-endpoint dependencies (security §7).
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError as SAOperationalError
from sqlalchemy.exc import TimeoutError as SATimeoutError

from app.api.v1 import (
    ai, ai_config, auth, documents, excel_mapping_chat, exports, learning, legacy_sql_converter,
    platform, reports, rule_chat, schedules, semantic, templates, validations,
)
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.pg_migrate import run_pg_migrations_if_enabled
from app.db.postgres import init_postgres_database
from app.db.pg_tenant_session import init_postgres_tenant_session_manager

configure_logging()
log = get_logger("app")

init_postgres_database()
init_postgres_tenant_session_manager()
run_pg_migrations_if_enabled()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Assisted Self-Service Report Builder — REST/JSON over FastAPI (README §3.1).",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS for the two SPAs (tighten origins per environment in deployment).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "local" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _operational_error_detail(request: Request, exc: SAOperationalError) -> str:
    """Map SQLAlchemy connection errors to actionable copy (not everything is VPN)."""
    raw = str(getattr(exc, "orig", exc) or exc)
    err = raw.lower()
    path = request.url.path
    api = settings.api_v1_prefix

    datamart_op = (
        path.startswith(f"{api}/reports")
        or path.startswith(f"{api}/exports")
        or path.endswith("/coverage")
        or path.endswith("/rebuild")
        or "/preview" in path
        or "/render" in path
    )

    if "does not exist" in err and "database" in err:
        if datamart_op:
            return (
                "This tenant's reporting warehouse is not set up yet. "
                "Ask Mint support to provision the datamart for this customer, then try again."
            )
        return "Report Builder storage is not configured correctly. Contact your administrator."

    if "authentication failed" in err or ("password" in err and "failed" in err):
        return "Database authentication failed. Contact your administrator to verify Report Builder credentials."

    if any(
        token in err
        for token in (
            "connection refused",
            "could not connect",
            "timed out",
            "timeout expired",
            "network is unreachable",
            "no route to host",
            "could not translate host name",
        )
    ):
        if datamart_op:
            return (
                "Could not reach this tenant's reporting warehouse. "
                "If your site uses a VPN to the datamart, connect and try again."
            )
        return "Report Builder could not reach its storage database. Try again shortly or contact support."

    if datamart_op:
        return "Could not read from the reporting warehouse for this tenant. Try again or contact support."

    if path.startswith(f"{api}/semantic"):
        return "Could not load the field catalogue. Try again or contact support."

    return "A database error occurred. Try again or contact support."


@app.exception_handler(SATimeoutError)
async def _db_pool_exhausted(request: Request, exc: SATimeoutError) -> JSONResponse:
    """QueuePool checkout timeout — retryable, not a schema/provisioning bug."""
    log.warning("database_pool_exhausted", path=request.url.path, error=str(exc)[:200])
    return JSONResponse(
        status_code=503,
        content={"detail": "Report Builder is busy. Try again in a moment."},
    )


@app.exception_handler(SAOperationalError)
async def _db_unreachable(request: Request, exc: SAOperationalError) -> JSONResponse:
    """Turn database connection failures into clear, retryable messages."""
    detail = _operational_error_detail(request, exc)
    log.warning("database_unreachable", path=request.url.path, error=str(exc)[:200], detail=detail)
    return JSONResponse(status_code=503, content={"detail": detail})


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


_API = settings.api_v1_prefix
for router in (auth, semantic, templates, reports, ai, ai_config, rule_chat, excel_mapping_chat, legacy_sql_converter, exports, schedules, documents, validations, learning, platform):
    app.include_router(router.router, prefix=_API)
