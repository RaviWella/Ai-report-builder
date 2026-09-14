"""Query Engine guards (Architecture §7.1, NFR-1/NFR-3).

These are the deterministic safety checks applied to every compiled query:
  - all refs exist in the pinned semantic catalogue (no free-form columns)
  - only declared joins are used (no inferred cross-entity access)
  - a row limit and statement timeout are always present
  - the produced statement is read-only (SELECT only)

Tenant scoping itself is enforced at connection level (db/datamart.py: read-only
user + search_path locked to the tenant's schema). These guards are the in-engine
second line of defense.
"""

from __future__ import annotations

import re

from app.core.config import settings
from app.domain.report_spec import DataSpec
from app.domain.semantic import SemanticCatalog


class GuardError(ValueError):
    """Raised when a spec violates a safety guard. Maps to HTTP 400."""


def validate_refs(spec: DataSpec, catalog: SemanticCatalog) -> None:
    """Every ref used anywhere in the spec must resolve in the catalogue."""
    known = set(catalog.field_index().keys())
    # calculated fields introduce virtual refs "calc.<name>"
    known |= {f"calc.{c.name}" for c in spec.calculated_fields}
    # canonical metrics introduce virtual refs "metric.<key>"
    known |= {f"metric.{m.key}" for m in catalog.metrics}

    unknown = {r for r in spec.all_refs() if r not in known}
    if unknown:
        raise GuardError(f"Unknown semantic refs (not in pinned catalogue): {sorted(unknown)}")

    if spec.entity not in catalog.entity_by_key():
        raise GuardError(f"Unknown root entity: {spec.entity!r}")


def validate_joins(spec: DataSpec, catalog: SemanticCatalog) -> None:
    """Any non-root entity referenced must be reachable through a DECLARED join."""
    # calc.* are virtual; metric.<k> expands to its underlying field entities.
    entity_keys = {r.split(".", 1)[0] for r in catalog.expand_field_refs(spec.all_refs())}
    # The root tracks the chosen fields (not the builder's default), so a report
    # built purely from a standalone entity still validates.
    root_key = catalog.root_for(entity_keys, spec.entity)
    entity_keys.discard(root_key)

    # Build adjacency from declared joins (keyed by entity key, not display name).
    name_to_key = {e.name: e.key for e in catalog.entities}
    reachable = {root_key}
    changed = True
    while changed:
        changed = False
        for j in catalog.joins:
            lk = name_to_key.get(j.left_entity, j.left_entity)
            rk = name_to_key.get(j.right_entity, j.right_entity)
            if lk in reachable and rk not in reachable:
                reachable.add(rk)
                changed = True
            if rk in reachable and lk not in reachable:
                reachable.add(lk)
                changed = True

    unreachable = entity_keys - reachable
    if unreachable:
        key_to_name = {e.key: e.name for e in catalog.entities}
        root = key_to_name.get(root_key, root_key)
        names = ", ".join(sorted(key_to_name.get(k, k) for k in unreachable))
        raise GuardError(
            f"This report mixes fields that can’t be combined with “{root}”: {names}. "
            "These are standalone summaries — build each one as its own report "
            "(remove those fields here, or start a new report from that dataset)."
        )


def resolve_row_limit(*, preview: bool, requested: int | None = None) -> int:
    cap = settings.preview_row_limit if preview else settings.query_row_limit
    if requested is None:
        return cap
    return min(requested, cap)


# Any write / DDL / DCL / procedural keyword. The datamart is strictly read-only:
# ONLY SELECT (and calculations within it) are ever allowed. Defense layer 3 of 3
# (1 = read-only DB user, 2 = read-only transaction; see db/datamart.py).
_FORBIDDEN_KEYWORDS = frozenset(
    {
        "insert", "update", "delete", "merge", "upsert", "truncate", "drop",
        "create", "alter", "replace", "rename", "grant", "revoke", "comment",
        "copy", "call", "do", "execute", "vacuum", "analyze", "cluster", "reindex",
        "lock", "refresh", "set", "reset", "begin", "commit", "rollback", "savepoint",
        "prepare", "deallocate", "listen", "notify", "discard", "import", "load",
        "into",  # blocks SELECT … INTO (creates a table)
    }
)
_WORD = re.compile(r"[a-z_][a-z0-9_]*")


def assert_select_only(sql_text: str) -> None:
    """Final belt-and-braces: the compiled statement must be a single read-only
    SELECT. The Query Engine only ever builds SELECTs, so anything else is a bug —
    AND a refusal. No INSERT/UPDATE/DELETE/DDL is ever permitted on the datamart;
    only SELECT + calculations.

    This is one of three independent read-only layers; even if a string slipped
    past it, the read-only DB user and read-only transaction would still reject it.
    """
    stripped = sql_text.strip()
    if not stripped:
        raise GuardError("Empty statement — refusing to run")

    head = stripped.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise GuardError(
            f"Query Engine produced a non-SELECT statement (starts with {head!r}) — refusing to run"
        )

    # Single statement only — a ';' could chain a second (write) statement.
    # (A trailing ';' with nothing after is also rejected for simplicity.)
    if ";" in sql_text:
        raise GuardError("Compiled SQL contains ';' (multiple statements) — refusing to run")

    # No write/DDL/DCL/procedural keyword anywhere (word-boundary matched).
    # Strip quoted identifiers ("col") and string literals ('text') first, so a
    # column label like "Promoted Into Senior" can't trip a keyword match.
    code = re.sub(r'"[^"]*"', " ", sql_text.lower())
    code = re.sub(r"'[^']*'", " ", code)
    hit = set(_WORD.findall(code)) & _FORBIDDEN_KEYWORDS
    if hit:
        raise GuardError(f"Compiled SQL contains forbidden keyword(s): {sorted(hit)} — refusing to run")
