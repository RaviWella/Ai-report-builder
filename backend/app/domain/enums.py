"""Shared enums for specs, roles, and lifecycle. Pure domain — no I/O."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """RBAC roles (SRS §9)."""

    SUPPORT_ADMIN = "support_admin"  # MintHRM support: any tenant, manage semantic layer
    CLIENT_HR_ADMIN = "client_hr_admin"  # Builder within own tenant
    CLIENT_END_USER = "client_end_user"  # Viewer only, own tenant
    SYSTEM = "system"  # backend / tech team


class FilterOp(str, Enum):
    """Comparison operators (FR-B2). Whitelist — the Query Engine maps these to
    SQLAlchemy expressions; no operator string ever reaches raw SQL."""

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"
    IN = "in"
    CONTAINS = "contains"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class AggFn(str, Enum):
    """Aggregation functions (FR-B3)."""

    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MIN = "min"
    MAX = "max"


class SortDir(str, Enum):
    ASC = "asc"
    DESC = "desc"


class FieldType(str, Enum):
    """Semantic field data types (locally inferred; drives formatting + op validity)."""

    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class FieldRole(str, Enum):
    """Kimball roles surfaced to the builder."""

    DIMENSION = "dimension"
    MEASURE = "measure"


class ParamType(str, Enum):
    """Runtime parameter types bound at view-time (FR-V2)."""

    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    DATE_RANGE = "date_range"
    BOOLEAN = "boolean"
    ENUM = "enum"


class VersionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ExportFormat(str, Enum):
    XLSX = "xlsx"
    PDF = "pdf"


class AIInputMode(str, Enum):
    """The two interleavable input modes in one session (SRS §5.2)."""

    CHAT = "chat"
    EXCEL = "excel"


class AuditAction(str, Enum):
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    TEMPLATE_DELETED = "template_deleted"
    VERSION_PUBLISHED = "version_published"
    VERSION_ROLLED_BACK = "version_rolled_back"
    REPORT_RUN = "report_run"
    REPORT_EXPORTED = "report_exported"
    SEMANTIC_UPDATED = "semantic_updated"
    AI_INTERACTION = "ai_interaction"
    AI_CONFIG_UPDATED = "ai_config_updated"
    SCHEDULE_CREATED = "schedule_created"
    SCHEDULE_TRIGGERED = "schedule_triggered"
