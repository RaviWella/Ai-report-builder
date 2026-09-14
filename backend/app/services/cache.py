"""In-process TTL + LRU cache utility.

Ported from mint-analytics. Used for schema inspection results, RLS values,
and optionally query results. Thread-safe, bounded, drop-in Redis replacement.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional, Tuple


class TTLCache:
    """Thread-safe LRU cache with per-entry TTL.

    - max_size: maximum number of entries (LRU eviction when exceeded)
    - default_ttl: default TTL in seconds for set() calls
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: OrderedDict[Any, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: Any) -> Optional[Any]:
        """Return value if present and not expired; refreshes LRU position."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at < time.time():
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            ttl = ttl if ttl is not None else self.default_ttl
            self._store[key] = (value, time.time() + ttl)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def delete(self, key: Any) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def stats(self) -> dict:
        with self._lock:
            now = time.time()
            valid = sum(1 for _, (_, exp) in self._store.items() if exp >= now)
            return {
                "total": len(self._store),
                "valid": valid,
                "expired": len(self._store) - valid,
                "max_size": self.max_size,
            }


# ── Shared instances ─────────────────────────────────────────────
schema_cache = TTLCache(max_size=10_000, default_ttl=300)   # schemas/tables/fields — 5 min
rls_cache    = TTLCache(max_size=50_000, default_ttl=300)   # per (rule, user) — 5 min
query_cache  = TTLCache(max_size=5_000,  default_ttl=60)    # query results — 1 min
