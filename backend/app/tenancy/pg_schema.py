"""Map request subdomain headers to PostgreSQL schema names."""

from __future__ import annotations

import re

from app.core.exceptions import InvalidTenantSchemaError
from app.tenancy.subdomain import normalize_subdomain

SCHEMA_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

RESERVED_SCHEMAS = frozenset(
    {
        "public",
        "platform",
        "information_schema",
        "pg_catalog",
        "pg_toast",
    }
)


def subdomain_to_pg_schema(subdomain: str) -> str:
    """Convert a tenant code to a PostgreSQL schema name (e.g. lk-minthrm → lk_minthrm)."""
    schema_name = normalize_subdomain(subdomain)
    return validate_pg_schema_name(schema_name)


def validate_pg_schema_name(schema_name: str) -> str:
    if not schema_name or not SCHEMA_NAME_RE.match(schema_name):
        raise InvalidTenantSchemaError(
            schema_name,
            "must match [a-z][a-z0-9_]{0,62}",
        )
    if schema_name in RESERVED_SCHEMAS or schema_name.startswith("pg_"):
        raise InvalidTenantSchemaError(schema_name, "reserved PostgreSQL schema name")
    return schema_name


def validate_template_schema(schema_name: str) -> str:
    """Validate the DDL source schema (defaults to public)."""
    normalized = schema_name.strip().lower()
    if normalized == "public":
        return normalized
    return validate_pg_schema_name(normalized)
