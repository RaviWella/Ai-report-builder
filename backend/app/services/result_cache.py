"""Redis-backed result cache for report queries.

Why: every report run otherwise hits the per-tenant datamart live over a flaky
VPN; two users running the same report = two warehouse round-trips. This caches
the compiled QueryResult so an identical run is served from Redis.

Correct-by-construction freshness: the datamart load-watermark
(`datamart_snapshot_ref`) is PART of the cache key. When the warehouse refreshes,
the watermark changes -> the key changes -> stale entries are simply unreachable.
There is no explicit invalidation and a stale snapshot is never served; the TTL is
only a safety net. We cache ONLY when a snapshot_ref is available — without a
freshness anchor we don't risk serving stale data (and when the VPN is fully down
both the watermark read and the data query fail anyway, so there's nothing to
cache).

Single-flight: on a miss, one caller computes while others briefly wait on the
result, so a popular report expiring doesn't stampede the datamart.

Every Redis interaction is best-effort and wrapped — any cache/redis failure
degrades to "no cache", never breaking a report run. Serialization is pickle+zlib
(the cache is internal and trusted); `QueryResult` is reconstructed by pickle via
its module path, so this module never imports it (no import cycle with the runner).
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
import zlib
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_KEY_VERSION = "v1"  # bump to invalidate the whole cache shape


def _params_hash(params: dict[str, Any]) -> str:
    blob = json.dumps(params or {}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def make_key(tenant_id: str, sql_hash: str, params: dict[str, Any], snapshot_ref: str) -> str:
    """Content-addressed by data version: same tenant + SQL + params + snapshot ->
    same key; a warehouse refresh (new snapshot) -> new key (old one unreachable)."""
    raw = f"{_KEY_VERSION}|{tenant_id}|{sql_hash}|{_params_hash(params)}|{snapshot_ref}"
    return "rc:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def encode(result: object) -> bytes:
    return zlib.compress(pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))


def decode(blob: bytes) -> object:
    return pickle.loads(zlib.decompress(blob))  # noqa: S301 - internal trusted cache


class ResultCache:
    """Thin wrapper over a Redis client. One instance per process (see `cache()`)."""

    def __init__(self) -> None:
        self._client = None
        self._init_done = False

    # -- connection (lazy, fail-safe) --
    def _conn(self):  # noqa: ANN202
        if not settings.result_cache_enabled:
            return None
        if not self._init_done:
            self._init_done = True
            try:
                import redis  # local import: optional dependency

                client = redis.Redis.from_url(
                    settings.result_cache_url,
                    socket_timeout=0.5, socket_connect_timeout=0.5,
                )
                client.ping()
                self._client = client
                log.info("result_cache_connected", url=settings.result_cache_url)
            except Exception as exc:  # noqa: BLE001 - cache is optional; never break a run
                log.warning("result_cache_unavailable", error=str(exc)[:160])
                self._client = None
        return self._client

    @property
    def enabled(self) -> bool:
        return self._conn() is not None

    # -- read / write --
    def get(self, key: str) -> Any | None:
        c = self._conn()
        if c is None:
            return None
        try:
            blob = c.get(key)
            return decode(blob) if blob is not None else None
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_get_failed", error=str(exc)[:160])
            return None

    def set(self, key: str, result: object, ttl: int | None = None) -> None:
        c = self._conn()
        if c is None:
            return
        try:
            blob = encode(result)
            if len(blob) > settings.result_cache_max_bytes:
                log.info("result_cache_skip_large", bytes=len(blob))
                return
            c.set(key, blob, ex=ttl if ttl is not None else settings.result_cache_ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_set_failed", error=str(exc)[:160])

    def delete(self, key: str) -> None:
        c = self._conn()
        if c is None:
            return
        try:
            c.delete(key)
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_delete_failed", error=str(exc)[:160])

    # -- single-flight --
    def acquire(self, key: str) -> bool:
        """True if THIS caller should compute (won the lock). False if someone else
        holds it (the caller should wait via `wait_for`)."""
        c = self._conn()
        if c is None:
            return True  # no cache -> everyone just computes
        try:
            return bool(c.set(key + ":lock", "1", nx=True, ex=settings.result_cache_lock_ttl_seconds))
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_lock_failed", error=str(exc)[:160])
            return True

    def release(self, key: str) -> None:
        c = self._conn()
        if c is None:
            return
        try:
            c.delete(key + ":lock")
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_unlock_failed", error=str(exc)[:160])

    def wait_for(self, key: str) -> Any | None:
        """Poll for an in-flight computation's result up to `result_cache_wait_ms`.
        Returns the result if it lands in time, else None (caller falls through to
        compute itself — correctness over a missed cache)."""
        if self._conn() is None:
            return None
        deadline = time.monotonic() + settings.result_cache_wait_ms / 1000.0
        while time.monotonic() < deadline:
            hit = self.get(key)
            if hit is not None:
                return hit
            time.sleep(0.05)
        return None


_CACHE: ResultCache | None = None


def cache() -> ResultCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = ResultCache()
    return _CACHE


def cached_snapshot_ref(ctx, datamart_key: str) -> str | None:
    """The datamart load-watermark for the tenant, reused from Redis for a short TTL
    so cache-hit runs don't re-query the warehouse just to build the key. Falls back
    to a live read (and caches it). Best-effort; returns None if unavailable."""
    from app.services.datamart_freshness import read_snapshot_ref

    c = cache()._conn()
    wkey = f"rc:wm:{ctx.tenant_id}:{datamart_key}"
    if c is not None:
        try:
            cached = c.get(wkey)
            if cached is not None:
                val = cached.decode() if isinstance(cached, bytes) else str(cached)
                return val or None
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_wm_get_failed", error=str(exc)[:160])
    snapshot = read_snapshot_ref(ctx, datamart_key)
    if c is not None and snapshot is not None:
        try:
            c.set(wkey, snapshot, ex=settings.result_cache_watermark_ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            log.warning("result_cache_wm_set_failed", error=str(exc)[:160])
    return snapshot
