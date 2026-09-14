"""Application health / readiness checks for load balancers and CI."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.application_db import connection_parts, get_application_engine_sync
from app.core.config import settings


def check_application_health() -> dict[str, Any]:
    """Verify control-plane DB connectivity and Alembic revision is recorded."""
    checks: dict[str, Any] = {}
    healthy = True

    try:
        parts = connection_parts(settings.application_database_url)
        checks["application_database"] = parts["database"]
    except Exception as exc:
        checks["application_database"] = f"config_error: {exc}"
        healthy = False

    try:
        engine = get_application_engine_sync()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            checks["database_ping"] = "ok"
            try:
                revision = conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar()
                checks["alembic_revision"] = revision or "unknown"
                if not revision:
                    checks["migrations"] = "alembic_version empty"
                    healthy = False
                else:
                    checks["migrations"] = "ok"
            except Exception as exc:
                checks["migrations"] = f"alembic_version missing: {exc}"
                healthy = False
        engine.dispose()
    except Exception as exc:
        checks["database_ping"] = str(exc)
        healthy = False

    try:
        from app.services.ai_services.datamart.llm.llm_settings import probe_datamart_llm

        checks["datamart_llm"] = probe_datamart_llm()
    except Exception as exc:  # noqa: BLE001
        checks["datamart_llm"] = {"status": "check_failed", "detail": str(exc)[:300]}

    return {
        "status": "healthy" if healthy else "unhealthy",
        "service": settings.APP_NAME,
        "checks": checks,
    }
