"""MintHRM SQLAlchemy models.

Shared/control tables (hrm_control schema) are managed by alembic.
Per-tenant ad-hoc connection tables (database_connections, data_access_rules)
live in each tenant's mart schema and are cloned from public on first use.
"""
from app.models.tenant_registry import TenantRegistry
from app.models.tenant_custom_report import TenantCustomReport
from app.models.database_connection import DatabaseConnection, DataAccessRule
from app.models.datamart_chat import (
    DatamartChatSession,
    DatamartChatMessage,
    DatamartChatSummary,
)
from app.models.datamart_workspace import (
    DatamartSessionGroup,
    DatamartTemplateGroup,
    DatamartTemplate,
    DatamartTemplateVersion,
)

__all__ = [
    "TenantRegistry",
    "TenantCustomReport",
    "DatabaseConnection",
    "DataAccessRule",
    "DatamartChatSession",
    "DatamartChatMessage",
    "DatamartChatSummary",
    "DatamartSessionGroup",
    "DatamartTemplateGroup",
    "DatamartTemplate",
    "DatamartTemplateVersion",
]
