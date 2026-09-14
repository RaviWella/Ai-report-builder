"""Data Access Service — Row-Level Security via external API.

Ported from mint-analytics. Rewrites ad-hoc SQL queries to add
WHERE target_column IN (values_from_external_api) filters before execution.

Flow:
  1. User sends query with context (permission_level_id, user_id, tenant_id)
  2. QueryEngine calls apply_rls() before executing
  3. For each active DataAccessRule on the connection:
     a. Calls the external module API with the user's context
     b. Extracts allowed values from the response
     c. Wraps the SQL: SELECT * FROM (...) AS _rls WHERE col IN (values)
  4. Returns the rewritten SQL
"""
from __future__ import annotations

import fnmatch
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database_connection import DataAccessRule
from app.services.cache import rls_cache

logger = logging.getLogger("data_access")


# ── Cache helpers ────────────────────────────────────────────────

def _cache_key(rule_id: int, context: Dict[str, str]) -> tuple:
    return (
        "rls",
        rule_id,
        context.get("permission_level_id", ""),
        context.get("user_id", ""),
        context.get("tenant_id", ""),
    )


# ── External API caller ──────────────────────────────────────────

def _resolve_placeholders(template: Any, context: Dict[str, str]) -> Any:
    """Replace {placeholder} tokens in strings/dicts/lists with context values."""
    if isinstance(template, str):
        for k, v in context.items():
            template = template.replace(f"{{{k}}}", str(v))
        return template
    if isinstance(template, dict):
        return {k: _resolve_placeholders(v, context) for k, v in template.items()}
    if isinstance(template, list):
        return [_resolve_placeholders(item, context) for item in template]
    return template


def _extract_single(data: Any, path: str) -> Any:
    for part in path.split("."):
        if isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return data


def _extract_values(data: Any, path: str) -> List[str]:
    """Extract values from a nested dict/list using dot-path notation.

    Supports:
      "data.emp_nos"         → data["data"]["emp_nos"]  (expects list)
      "data.users[].emp_no"  → [u["emp_no"] for u in data["data"]["users"]]
      "eligible_users"       → data["eligible_users"]   (expects list)
    """
    parts = path.split(".")
    current = data

    for part in parts:
        if part.endswith("[]"):
            key = part[:-2]
            if key:
                current = current.get(key, []) if isinstance(current, dict) else []
            remaining = ".".join(parts[parts.index(part) + 1:])
            if remaining and isinstance(current, list):
                return [
                    str(_extract_single(item, remaining))
                    for item in current
                    if _extract_single(item, remaining) is not None
                ]
            return [str(v) for v in current] if isinstance(current, list) else []
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return []

    if isinstance(current, list):
        return [str(v) for v in current]
    if current is not None:
        return [str(current)]
    return []


def _call_external_api(rule: DataAccessRule, context: Dict[str, str]) -> List[str]:
    """Call the external module API and extract allowed values.

    Fails closed — returns [] on any error so the user sees no rows rather
    than bypassing security.
    """
    url = _resolve_placeholders(rule.external_api_url, context)
    headers = _resolve_placeholders(rule.external_api_headers or {}, context)
    body = _resolve_placeholders(rule.external_api_body or {}, context)
    method = (rule.external_api_method or "POST").upper()

    logger.info("[RLS] Calling external API: %s %s", method, url)
    try:
        with httpx.Client(timeout=15.0) as client:
            if method == "GET":
                resp = client.get(url, headers=headers, params=body)
            else:
                resp = client.request(method, url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        values = _extract_values(data, rule.response_values_path)
        logger.info("[RLS] Rule '%s': got %d allowed values", rule.name, len(values))
        return values
    except Exception as exc:
        logger.error("[RLS] External API call failed for rule '%s': %s", rule.name, exc)
        return []  # fail closed


# ── Rule matching ────────────────────────────────────────────────

def _tables_in_sql(sql: str) -> List[str]:
    pattern = r'(?:FROM|JOIN)\s+(?:"?(\w+)"?\.)?"?(\w+)"?'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return [m[1] for m in matches]


def _rule_applies_to_sql(rule: DataAccessRule, sql: str) -> bool:
    patterns = rule.apply_to_tables or []
    if not patterns or patterns == ["*"]:
        return True
    tables = _tables_in_sql(sql)
    for table in tables:
        for pattern in patterns:
            if fnmatch.fnmatch(table.lower(), pattern.lower()):
                return True
    return False


# ── SQL rewriting ────────────────────────────────────────────────

def _rewrite_sql(sql: str, target_column: str, allowed_values: List[str]) -> str:
    """Wrap SQL with a WHERE IN filter on target_column.

    No allowed values → return 0 rows (fail closed).
    """
    if not allowed_values:
        return f"SELECT * FROM ({sql.rstrip(';')}) AS _rls WHERE 1=0"

    safe_values = ", ".join(
        f"'{v.replace(chr(39), chr(39) + chr(39))}'" for v in allowed_values
    )
    col = (
        f'"{target_column}"'
        if target_column != target_column.lower() or not target_column.isalnum()
        else target_column
    )
    return f"SELECT * FROM ({sql.rstrip(';')}) AS _rls WHERE _rls.{col} IN ({safe_values})"


# ── Public API ───────────────────────────────────────────────────

def get_active_rules(db: Session, connection_id: int) -> List[DataAccessRule]:
    result = db.execute(
        select(DataAccessRule)
        .where(DataAccessRule.connection_id == connection_id)
        .where(DataAccessRule.is_active == True)
        .order_by(DataAccessRule.priority.desc())
    )
    return list(result.scalars().all())


def apply_rls(
    db: Session,
    connection_id: int,
    sql: str,
    user_context: Dict[str, str],
) -> str:
    """Apply all active RLS rules to a SQL query and return the rewritten SQL."""
    rules = get_active_rules(db, connection_id)
    if not rules:
        return sql

    user_role = user_context.get("role", "")
    applicable = [
        r for r in rules
        if not (r.applies_to_roles or []) or user_role in r.applies_to_roles
    ]
    if not applicable:
        return sql

    rewritten = sql
    for rule in applicable:
        if not _rule_applies_to_sql(rule, rewritten):
            continue

        ck = _cache_key(rule.id, user_context)
        allowed: Optional[List[str]] = rls_cache.get(ck)
        if allowed is None:
            allowed = _call_external_api(rule, user_context)
            rls_cache.set(ck, allowed, ttl=rule.cache_ttl_seconds or 300)

        rewritten = _rewrite_sql(rewritten, rule.target_column, allowed)
        logger.info(
            "[RLS] Applied rule '%s': filtered on %s (%d values)",
            rule.name, rule.target_column, len(allowed),
        )

    return rewritten
