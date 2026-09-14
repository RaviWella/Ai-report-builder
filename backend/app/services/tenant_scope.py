"""Resolve datamart_key from platform.tenant_provision_status.

Cached in the shared (Redis-backed) result cache — NOT a per-process dict.
Production runs multiple workers; a per-process cache leaves every OTHER
worker serving a stale key indefinitely after a fix, with no way to force a
refresh short of restarting every worker. The TTL (datamart_key_cache_ttl_seconds)
is a safety net; explicit invalidation via clear_datamart_key_cache() — called
by every code path that writes a new datamart_key — is the real mechanism.
Like the rest of the result cache, a missing/disabled Redis degrades to
"always resolve live", never to a wrong or unrefreshable answer.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.postgres import get_postgres_database
from app.repositories.tenant_provision import get_datamart_key
from app.services import result_cache

_KEY_PREFIX = "dmk:"


def _cache_key(tenant_id: str) -> str:
    return f"{_KEY_PREFIX}{tenant_id}"


def clear_datamart_key_cache(tenant_id: str) -> None:
    result_cache.cache().delete(_cache_key(tenant_id))


def resolve_datamart_key(tenant_id: str) -> str:
    """Look up warehouse DB key for a tenant (platform schema)."""
    key = _cache_key(tenant_id)
    cached = result_cache.cache().get(key)
    if cached is not None:
        return cached
    pg = get_postgres_database().session()
    try:
        pg.execute(text("SET search_path TO platform, public"))
        value = get_datamart_key(pg, tenant_id)
        result_cache.cache().set(key, value, ttl=settings.datamart_key_cache_ttl_seconds)
        return value
    finally:
        pg.close()


def resolve_datamart_key_from_session(db: Session, tenant_id: str) -> str:
    """Best-effort datamart key when already in a tenant session (uses tenant_id fallback)."""
    return tenant_id
