"""Configurable source table/column mapping for MintHRM extractors.

Physical names live in YAML under ``mappings/``; extractors use *logical* keys
(``emp_basic``, ``employee.id``) so MySQL MintHRM and a different PostgreSQL
schema can share the same Python code.

Files (first match wins for tenant override):
  mappings/{profile}_{variant}.yaml
  mappings/overrides/{tenant_id}.yaml   (optional deep-merge)

Env:
  SOURCE_MAPPING_PROFILE  — default: MYSQL_EXTRACTOR_PROFILE (e.g. minthrm)
  SOURCE_MAPPING_VARIANT  — default: source_type (mysql | postgres)
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

import yaml

from app.core.config import settings
from app.services.hr_etl.source_connection import SourceType, get_dialect, normalize_source_type

logger = logging.getLogger("hr_etl.mapping")

_MAPPINGS_DIR = Path(__file__).resolve().parent / "mappings"

_current_mapping: ContextVar["SourceMapping | None"] = ContextVar(
    "etl_source_mapping", default=None
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _quote_table(name: str) -> str:
    """Quote table/view identifiers when required (reserved words, mixed case)."""
    if not name:
        return name
    if get_dialect() == "postgres":
        if name.islower() and name.replace("_", "").isalnum():
            return name
        return f'"{name}"'
    return f"`{name}`"


class SourceMapping:
    """Resolved physical schema for one profile + variant (+ optional tenant)."""

    def __init__(self, data: dict[str, Any], *, profile: str, variant: str):
        self.profile = profile
        self.variant = variant
        self.source_schema: str | None = data.get("source_schema") or None
        self.tables: dict[str, str] = dict(data.get("tables") or {})
        self.columns: dict[str, dict[str, str]] = {
            k: dict(v) for k, v in (data.get("columns") or {}).items()
        }
        self.expressions: dict[str, str] = dict(data.get("expressions") or {})
        self.disabled_tables: set[str] = set(data.get("disabled_tables") or [])

    def table(self, key: str) -> str:
        if key in self.disabled_tables:
            raise KeyError(f"Table '{key}' is disabled in mapping profile")
        physical = self.tables.get(key)
        if not physical:
            raise KeyError(
                f"Unknown table key '{key}' in mapping {self.profile}_{self.variant}. "
                f"Add it under tables: in YAML."
            )
        if self.source_schema:
            return _quote_table(f"{self.source_schema}.{physical}")
        return _quote_table(physical)

    def physical_col(self, table_key: str, logical: str) -> str:
        cols = self.columns.get(table_key) or {}
        physical = cols.get(logical)
        if not physical:
            raise KeyError(
                f"Unknown column '{table_key}.{logical}' in mapping "
                f"{self.profile}_{self.variant}"
            )
        return physical

    def col(self, table_key: str, logical: str, alias: str | None = None) -> str:
        physical = self.physical_col(table_key, logical)
        if alias:
            return f"{alias}.{physical}"
        return physical

    def ref(self, table_key: str, logical: str, alias: str) -> str:
        return self.col(table_key, logical, alias)

    def expr(self, name: str, **placeholders: str) -> str:
        """Named SQL expression from YAML (optional per-variant overrides)."""
        template = self.expressions.get(name)
        if not template:
            raise KeyError(f"Unknown expression '{name}' in mapping")
        out = template
        for key, val in placeholders.items():
            out = out.replace("{" + key + "}", val)
        return out

    def has_table(self, key: str) -> bool:
        return key in self.tables and key not in self.disabled_tables


def _mapping_path(profile: str, variant: str) -> Path:
    return _MAPPINGS_DIR / f"{profile}_{variant}.yaml"


def load_source_mapping(
    *,
    profile: str,
    variant: SourceType,
    tenant_id: str | None = None,
) -> SourceMapping:
    path = _mapping_path(profile, variant)
    if not path.is_file():
        raise FileNotFoundError(
            f"Source mapping file not found: {path}. "
            f"Copy mappings/minthrm_mysql.yaml to mappings/{profile}_{variant}.yaml"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if tenant_id:
        override = _MAPPINGS_DIR / "overrides" / f"{tenant_id}.yaml"
        if override.is_file():
            extra = yaml.safe_load(override.read_text(encoding="utf-8")) or {}
            data = _deep_merge(data, extra)
            logger.info("merged tenant mapping override %s", override.name)

    return SourceMapping(data, profile=profile, variant=variant)


def resolve_mapping_profile() -> str:
    explicit = (settings.SOURCE_MAPPING_PROFILE or "").strip().lower()
    if explicit:
        return explicit
    return (settings.MYSQL_EXTRACTOR_PROFILE or "generic").strip().lower()


def resolve_mapping_variant(source_type: SourceType) -> SourceType:
    explicit = (getattr(settings, "SOURCE_MAPPING_VARIANT", None) or "").strip().lower()
    if explicit:
        return normalize_source_type(explicit)
    return source_type


def get_source_mapping() -> SourceMapping:
    m = _current_mapping.get()
    if m is None:
        raise RuntimeError(
            "No source mapping in context. ETL runner must use source_mapping()."
        )
    return m


@contextmanager
def source_mapping(
    tenant_id: str,
    source_type: SourceType,
    *,
    profile: str | None = None,
    source_schema: str | None = None,
) -> Iterator[SourceMapping]:
    prof = profile or resolve_mapping_profile()
    variant = resolve_mapping_variant(source_type)
    mapping = load_source_mapping(profile=prof, variant=variant, tenant_id=tenant_id)
    if source_schema:
        mapping.source_schema = source_schema
    token = _current_mapping.set(mapping)
    logger.info(
        "source mapping tenant=%s profile=%s variant=%s schema=%s tables=%d",
        tenant_id,
        prof,
        variant,
        mapping.source_schema or "(default)",
        len(mapping.tables),
    )
    try:
        yield mapping
    finally:
        _current_mapping.reset(token)
