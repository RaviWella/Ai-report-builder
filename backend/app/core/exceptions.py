"""Domain exceptions for tenancy and PostgreSQL provisioning."""

from __future__ import annotations


class TenantError(Exception):
    """Base class for tenant-scoping failures."""


class InvalidTenantSchemaError(TenantError):
    def __init__(self, schema_name: str, reason: str) -> None:
        self.schema_name = schema_name
        self.reason = reason
        super().__init__(f"Invalid tenant schema {schema_name!r}: {reason}")


class TenantNotProvisionedError(TenantError):
    def __init__(self, subdomain: str) -> None:
        self.subdomain = subdomain
        super().__init__(f"Tenant {subdomain!r} is not provisioned for Report Builder")


class PostgresSchemaError(Exception):
    """PostgreSQL schema provisioning or migration failure."""
