"""Classify tenant ETL source layouts (product scenarios A/B/C)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from app.services.tenant_etl_sources import TenantEtlSourceRow

ScenarioId = Literal[
    "mysql_only",
    "one_mysql_multi_postgres",
    "postgres_only_multi",
    "postgres_only_single",
    "mixed_other",
    "legacy",
    "empty",
]


def _registered(rows: list[TenantEtlSourceRow]) -> list[TenantEtlSourceRow]:
    return [r for r in rows if r.id != 0]


def classify_etl_sources(rows: list[TenantEtlSourceRow]) -> dict[str, Any]:
    """Return counts and which product scenario (if any) matches."""
    registered = _registered(rows)
    mysql = [r for r in registered if r.source_type == "mysql"]
    pg = [r for r in registered if r.source_type == "postgres"]
    mysql_count = len(mysql)
    postgres_count = len(pg)

    if not registered:
        if rows:
            return {
                "active_scenario": "legacy",
                "mysql_count": 0,
                "postgres_count": 0,
                "total_registered": 0,
                "has_primary": False,
                "matches_product_scenario": False,
                "product_scenario": None,
                "etl_ready": True,
            }
        return {
            "active_scenario": "empty",
            "mysql_count": 0,
            "postgres_count": 0,
            "total_registered": 0,
            "has_primary": False,
            "matches_product_scenario": False,
            "product_scenario": None,
            "etl_ready": False,
        }

    active: ScenarioId
    product: Optional[str] = None
    matches = False

    if mysql_count >= 1 and postgres_count == 0:
        active, product, matches = "mysql_only", "A", True
    elif mysql_count == 1 and postgres_count >= 2:
        active, product, matches = "one_mysql_multi_postgres", "B", True
    elif mysql_count == 0 and postgres_count >= 2:
        active, product, matches = "postgres_only_multi", "C", True
    elif mysql_count == 0 and postgres_count == 1:
        active, product, matches = "postgres_only_single", None, False
    else:
        active, product, matches = "mixed_other", None, False

    primary_key = next((r.source_key for r in registered if r.is_primary), None)

    return {
        "active_scenario": active,
        "mysql_count": mysql_count,
        "postgres_count": postgres_count,
        "total_registered": len(registered),
        "has_primary": primary_key is not None,
        "primary_source_key": primary_key,
        "matches_product_scenario": matches,
        "product_scenario": product,
        "etl_ready": True,
        "sources": [
            {
                "source_key": r.source_key,
                "display_name": r.display_name,
                "source_type": r.source_type,
                "source_schema": r.source_schema,
                "is_primary": r.is_primary,
                "staging_suffix": r.staging_suffix or "(primary stg_*)",
            }
            for r in registered
        ],
    }
