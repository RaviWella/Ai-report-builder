"""Generate enterprise data dictionary markdown from warehouse + dbt metadata."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.warehouse import get_warehouse_engine_sync
from app.services.hr_etl.data_dictionary_schema import (
    _format_pg_type,
    sync_warehouse_dictionary,
)

from .staging_catalog import apply_staging_catalog_entry, build_staging_catalog
from .static_metadata import (
    AI_VIEW_METADATA,
    DATA_QUALITY_RULES,
    DEFAULT_GOVERNANCE,
    DOMAIN_GOVERNANCE,
    GLOSSARY,
    METRICS,
    PII_COLUMN_PATTERNS,
    SENSITIVE_COLUMN_PATTERNS,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPO_ROOT / "docs"
DBT_ROOT = REPO_ROOT / "backend" / "dbt_project" / "hr_mart"
META_PATH = DOCS_ROOT / "datamart-er.yml"
STAGING_DDL_PATH = REPO_ROOT / "backend" / "app" / "services" / "hr_etl" / "staging_ddl.py"
MAPPING_PATH = REPO_ROOT / "backend" / "app" / "services" / "hr_etl" / "mappings" / "minthrm_mysql.yaml"
SOURCES_PAYROLL_PATH = DBT_ROOT / "models" / "sources_payroll.yml"

WAREHOUSE_APP_TABLES = frozenset(
    {
        "database_connections",
        "data_access_rules",
        "schema_migrations",
        "alembic_version",
    }
)

WAREHOUSE_EXCLUDE_SUFFIXES = ("__dbt_test", "__dbt_tmp")

STAGING_PREFIX = "stg_"


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    column_default: str | None = None
    description: str = "TBD"
    source_column: str = "TBD"
    transformation: str = "TBD"
    pii: bool = False
    sensitive: bool = False
    ai_aliases: list[str] = field(default_factory=list)


@dataclass
class ObjectInfo:
    name: str
    schema_name: str
    object_type: str  # Table | View
    layer: str
    domain: str
    description: str = "TBD"
    grain: str = "TBD"
    primary_key: str = "TBD"
    business_key: str = "TBD"
    scd_type: str = "N/A"
    refresh_type: str = "Batch"
    refresh_frequency: str = "Daily"
    source_systems: list[str] = field(default_factory=list)
    consumers: list[str] = field(default_factory=lambda: ["Semantic Views", "Reports", "AI Agent"])
    contains_pii: bool = False
    columns: list[ColumnInfo] = field(default_factory=list)
    is_scd2: bool = False


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _infer_layer(name: str, schema: str) -> str:
    if schema == "hr_raw" or name.startswith(STAGING_PREFIX) or name.startswith("raw_"):
        return "Staging"
    if name.startswith("dim_"):
        return "Dimension"
    if name.startswith("fct_") or name.startswith("fact_"):
        return "Fact"
    if name.startswith("mart_"):
        return "Mart"
    if name.startswith("snap_") or schema == "hr_snap":
        return "Snapshot"
    if name.startswith("vw_") or schema == "hr_semantic":
        return "Semantic"
    return "Other"


def _infer_domain(name: str) -> str:
    lower = name.lower()
    if any(k in lower for k in ("leave", "lieu", "maternity", "short_leave")):
        return "Leave Management"
    if any(
        k in lower
        for k in (
            "payroll",
            "salary",
            "paysheet",
            "bank",
            "tax",
            "epf",
            "etf",
            "loan_ded",
            "compliance",
            "canonical_pay",
            "statutory",
            "ctc",
            "cost_to_company",
        )
    ):
        return "Payroll"
    if any(k in lower for k in ("attendance", "overtime", "shift")):
        return "Attendance"
    if any(k in lower for k in ("lifecycle", "headcount", "turnover", "employment")):
        return "Workforce"
    if name.startswith("dim_"):
        return "Workforce"
    return "Enterprise HR"


def _infer_pk(name: str, layer: str) -> str:
    if layer in ("Mart", "Semantic"):
        return "TBD"
    if name.startswith("dim_"):
        return f"{name[4:]}_sk"
    if name.startswith("fct_"):
        body = name[4:]
        return f"{body}_sk" if not body.endswith("_sk") else body
    if name.startswith("fact_"):
        return "id"
    if name.startswith("snap_"):
        return "dbt_scd_id"
    if name.startswith(("stg_", "raw_")):
        return "id"
    return "TBD"


# Columns that scope rows in the warehouse but are not business-natural keys.
_BUSINESS_KEY_SCOPE_COLS = frozenset(
    {
        "tenant_id",
        "source_system",
        "extracted_at",
        "_loaded_at",
        "_source_updated_at",
        "created_at",
        "updated_at",
        "load_date",
        "dbt_scd_id",
        "dbt_updated_at",
        "dbt_valid_from",
        "dbt_valid_to",
    }
)

# Manual overrides when dbt config / columns are insufficient.
_MODEL_BUSINESS_KEY_OVERRIDES: dict[str, str] = {
    "dim_employee": "source_emp_id, emp_no (+ valid_from for SCD2 version)",
    "snap_employee": "employee_nk",
    "snap_designation": "designation_nk",
    "snap_shift": "shift_nk",
    "snap_leave_type": "leave_type_nk",
    "dim_date": "date_sk (calendar surrogate) / calendar_date if present",
    "dim_org_unit": "source_org_unit_id / org_unit_code",
    "dim_designation": "source_designation_id / designation_code",
    "dim_shift": "source_shift_id / shift_code",
    "dim_leave_status": "status_code",
    "dim_leave_source": "leave_source_code",
    "dim_leave_reason": "source_reason_id / reason_code",
    "dim_leave_approval_level": "approval_level_code",
    "dim_payroll_period": "year, month, half",
    "dim_payroll_group": "source_payroll_group_id",
    "dim_canonical_pay_item": "canonical_pay_item_code",
    "fact_payroll": "same as fct_processed_salary (compatibility view)",
    "fact_leave_balance": "id (legacy bridge)",
    "data_dictionary_object": "tenant_id, schema_name, object_name",
    "data_dictionary_field": "object_id, field_name",
    "vw_data_dictionary": "schema_name, object_name, field_name",
}

# Staging tables whose only stable key in bronze is MintHRM id (no source_* yet).
_STAGING_ID_ONLY: frozenset[str] = frozenset(
    {
        "stg_employees",
        "stg_payroll_add_ded",
        "stg_payroll_attendance_lines",
        "stg_payroll_compliance_attendance",
        "stg_payroll_compliance_basic",
        "stg_payroll_details",
        "stg_payroll_installment_payments",
        "stg_payroll_loan_data",
        "stg_payroll_loan_deductions",
        "stg_payroll_non_consider_items",
        "stg_payroll_noncash_benefits",
        "stg_payroll_runs",
        "stg_payroll_salary_analyze",
        "stg_payroll_salary_analyze_data",
        "stg_payroll_salary_bank_data",
        "stg_payroll_salary_retrieve",
        "stg_payroll_tax",
        "stg_payroll_variable_additions",
        "stg_payroll_variable_deductions",
        "stg_prl_loan",
        "stg_leave_application_dates",
        "stg_leave_balance",
        "stg_leave_requests",
        "stg_lifecycle",
    }
)

_UNIQUE_KEY_RE_LIST = re.compile(
    r"unique_key\s*=\s*\[([^\]]+)\]",
    re.DOTALL,
)
_UNIQUE_KEY_RE_SCALAR = re.compile(r"unique_key\s*=\s*['\"]([^'\"]+)['\"]")


def load_dbt_unique_keys() -> dict[str, list[str]]:
    """Parse dbt model unique_key from SQL config blocks (model stem -> column list)."""
    keys: dict[str, list[str]] = {}
    search_roots = [
        DBT_ROOT / "models",
        DBT_ROOT / "snapshots",
    ]
    for root in search_roots:
        if not root.is_dir():
            continue
        for sql_path in root.rglob("*.sql"):
            try:
                head = sql_path.read_text(encoding="utf-8")[:2500]
            except OSError:
                continue
            if "unique_key" not in head:
                continue
            parsed: list[str] | None = None
            m_list = _UNIQUE_KEY_RE_LIST.search(head)
            if m_list:
                parsed = [
                    part.strip().strip("'\"")
                    for part in m_list.group(1).split(",")
                    if part.strip()
                ]
            else:
                m_scalar = _UNIQUE_KEY_RE_SCALAR.search(head)
                if m_scalar:
                    parsed = [m_scalar.group(1)]
            if parsed:
                keys[sql_path.stem] = parsed
    return keys


def _filter_business_key_columns(
    cols: list[str],
    *,
    layer: str,
    available: set[str],
) -> list[str]:
    """Drop warehouse scope/surrogate columns unless they define mart grain."""
    out: list[str] = []
    for col in cols:
        if col not in available:
            continue
        if col in _BUSINESS_KEY_SCOPE_COLS:
            continue
        if col.endswith("_sk") and layer not in ("Mart", "Semantic"):
            continue
        out.append(col)
    return out


def _natural_key_columns(col_names: list[str], obj_name: str, layer: str) -> list[str]:
    """Infer business-natural key columns from table columns."""
    col_set = set(col_names)
    source_cols = sorted(
        c for c in col_names if c.startswith("source_") and c != "source_system"
    )
    if source_cols:
        return source_cols[:6]

    entity = obj_name[4:] if obj_name.startswith("dim_") else ""
    candidates: list[str] = []
    if entity:
        candidates.extend(
            [
                f"{entity}_nk",
                f"source_{entity}_id",
                f"{entity}_id",
                f"{entity}_code",
                f"{entity}_no",
            ]
        )
    candidates.extend(
        [
            "emp_no",
            "status_code",
            "leave_source_code",
            "leave_status_code",
            "leave_reason_code",
            "approval_level_code",
            "bank_code",
            "branch_code",
            "canonical_pay_item_code",
            "payroll_group_code",
            "year",
            "month",
            "half",
            "calendar_date",
            "date_key",
            "code",
            "name",
        ]
    )
    found = [c for c in candidates if c in col_set]
    if found:
        return found[:5]

    if obj_name.startswith("fact_") and "id" in col_set:
        return ["id"]

    if obj_name.startswith("snap_") and "dbt_scd_id" in col_set:
        nk = f"{obj_name.replace('snap_', '')}_nk"
        if nk in col_set:
            return [nk]

    if layer in ("Mart", "Semantic"):
        grain_cols = [
            c
            for c in col_names
            if c.endswith("_sk")
            or c.endswith("_name")
            or c in ("year", "month", "month_number", "department_id", "snapshot_date", "date_sk")
        ]
        grain_cols = [c for c in grain_cols if c not in _BUSINESS_KEY_SCOPE_COLS]
        if grain_cols:
            return grain_cols[:6]

    return []


def _grain_business_key_hint(grain: str, col_names: list[str]) -> str | None:
    """Map ER grain text to likely column names when unique_key is absent."""
    if not grain or grain == "TBD":
        return None
    col_set = set(col_names)
    lower = grain.lower()
    parts: list[str] = []
    if "employee" in lower and "employee_sk" in col_set:
        parts.append("employee_sk")
    if "emp " in lower or "emp x" in lower:
        if "employee_sk" in col_set:
            parts.append("employee_sk")
    if "period" in lower:
        for c in ("payroll_period_sk", "year", "month", "half"):
            if c in col_set:
                parts.append(c)
    if "leave type" in lower and "leave_type_sk" in col_set:
        parts.append("leave_type_sk")
    if "department" in lower:
        for c in ("department_id", "department_name", "org_unit_sk"):
            if c in col_set:
                parts.append(c)
    if "date" in lower or "day" in lower:
        for c in ("date_sk", "snapshot_date", "start_date", "calendar_date"):
            if c in col_set:
                parts.append(c)
                break
    if "month" in lower and "month_number" in col_set:
        parts.append("month_number")
    if parts:
        return ", ".join(dict.fromkeys(parts))
    return None


def _staging_business_key(col_names: list[str]) -> str:
    """Bronze staging: MintHRM source PK (id) plus source_* / natural ids — not lookup codes alone."""
    col_set = set(col_names)
    source_cols = sorted(
        c for c in col_names if c.startswith("source_") and c != "source_system"
    )
    if source_cols:
        return ", ".join(source_cols[:6])

    parts: list[str] = []
    if "id" in col_set:
        parts.append("id")
    for c in (
        "employee_code",
        "employee_id",
        "emp_no",
        "application_id",
        "leave_id",
        "payroll_group_id",
        "bank_id",
        "branch_id",
    ):
        if c in col_set and c not in parts:
            parts.append(c)
    if parts:
        return ", ".join(parts)

    codes = [
        c
        for c in col_names
        if (c.endswith("_code") or c.endswith("_id"))
        and c not in _BUSINESS_KEY_SCOPE_COLS
        and not c.endswith("_sk")
        and c not in ("department_id", "designation_id", "branch_id")
    ]
    if codes:
        return ", ".join(codes[:4])
    return "id" if "id" in col_set else "TBD"


def _semantic_business_key(col_names: list[str]) -> str:
    """Semantic views: prefer keys/dates over display labels (employee_name)."""
    col_set = set(col_names)
    skip_suffixes = ("_name", "_label", "_description")
    key_cols = [
        c
        for c in col_names
        if c in col_set
        and not any(c.endswith(s) for s in skip_suffixes)
        and (
            c.endswith("_sk")
            or c.endswith("_id")
            or c.endswith("_no")
            or c in ("year", "month", "month_number", "snapshot_date", "emp_no", "date_sk")
        )
    ]
    key_cols = [c for c in key_cols if c not in _BUSINESS_KEY_SCOPE_COLS]
    if key_cols:
        return ", ".join(key_cols[:6])
    dims = [c for c in col_names if c.endswith("_id") or c == "emp_no"]
    if dims:
        return ", ".join(dims[:4])
    return "Query grain (see view SQL)"


def _enrich_staging_object(
    obj: ObjectInfo,
    staging_ddl: dict[str, list[tuple[str, str]]],
    staging_catalog: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Apply grain, description, and column hints to all hr_raw staging objects."""
    if obj.schema_name != "hr_raw" or not (
        obj.name.startswith("stg_") or obj.name.startswith("raw_")
    ):
        return

    entry = (staging_catalog or {}).get(obj.name)
    if entry:
        apply_staging_catalog_entry(obj, entry)
    elif "register extractor mapping" in (obj.description or "") or any(
        "TBD" in str(s) for s in (obj.source_systems or [])
    ):
        obj.description = "TBD"
        obj.source_systems = []

    if obj.grain == "TBD":
        obj.grain = "One row per MintHRM source record (typically id + extracted_at)"

    if obj.description == "TBD" or not obj.description.strip():
        if obj.source_systems:
            src = ", ".join(s for s in obj.source_systems[:3] if not s.startswith("("))
            obj.description = (
                f"Bronze staging landing from {src}."
                if src
                else "Bronze staging table (MintHRM extract landing zone)."
            )
        else:
            obj.description = "Bronze staging table (MintHRM extract landing zone)."

    for col in obj.columns:
        if col.name == "id" and (col.description == "TBD" or not col.description):
            col.description = "MintHRM source primary key"
            if obj.source_systems and not obj.source_systems[0].startswith("MintHRM"):
                col.source_column = f"{obj.source_systems[0]}.id"
        elif col.name == "extracted_at":
            col.description = "ETL extraction timestamp"
            col.source_column = "ETL"
        elif col.name in ("created_at", "updated_at") and col.source_column == "TBD":
            col.source_column = "MintHRM source audit columns"

    if obj.name in staging_ddl:
        ddl_cols = {c[0]: c[1] for c in staging_ddl[obj.name]}
        for col in obj.columns:
            if col.name in ddl_cols and col.data_type == "TBD":
                col.data_type = ddl_cols[col.name]


def _enrich_semantic_object(
    obj: ObjectInfo,
    semantic_reads: dict[str, str],
) -> None:
    if obj.layer != "Semantic" and not obj.name.startswith("vw_"):
        return
    reads = semantic_reads.get(obj.name, "")
    if obj.description == "TBD" or not obj.description.strip():
        obj.description = (
            f"Semantic API view over {reads}."
            if reads
            else "Semantic consumer view (stable API over physical marts)."
        )
    if obj.grain == "TBD":
        obj.grain = "One row per query result (inherits upstream mart/fact grain)"
    if obj.primary_key == "TBD":
        obj.primary_key = "-"


def _enrich_snapshot_object(obj: ObjectInfo, model_meta: dict[str, Any]) -> None:
    if obj.schema_name != "hr_snap" and not obj.name.startswith("snap_"):
        return
    entity = obj.name.replace("snap_", "")
    nk = f"{entity}_nk"
    if obj.grain == "TBD":
        meta_grain = (model_meta.get(f"dim_{entity}") or {}).get("grain")
        obj.grain = (
            f"SCD2 snapshot — {meta_grain}"
            if meta_grain
            else "SCD2 snapshot — one row per natural key version"
        )
    if obj.description == "TBD" or not obj.description.strip():
        obj.description = f"dbt snapshot history for dim_{entity} (feeds warehouse SCD2 dimensions)."
    col_set = {c.name for c in obj.columns}
    if obj.business_key in ("TBD",) and nk in col_set:
        obj.business_key = nk


def finalize_object_metadata(
    objects: dict[tuple[str, str], ObjectInfo],
    er_meta: dict[str, Any],
    *,
    payroll_src: dict[str, str] | None = None,
    dbt_meta: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Fill grain, description, and business_key after all discovery passes."""
    model_meta = er_meta.get("model_meta") or {}
    semantic_reads = {
        str(v.get("name", "")): str(v.get("reads", ""))
        for v in (er_meta.get("semantic_views") or [])
        if v.get("name")
    }
    staging_ddl = parse_staging_ddl()
    staging_catalog = build_staging_catalog(payroll_src or load_payroll_source_map())
    dbt_unique_keys = load_dbt_unique_keys()
    dbt_meta = dbt_meta or {}

    for obj in objects.values():
        if obj.name in dbt_meta and dbt_meta[obj.name].get("description"):
            if obj.description in ("TBD", "") or "register extractor" in obj.description:
                obj.description = dbt_meta[obj.name]["description"]
        _enrich_staging_object(obj, staging_ddl, staging_catalog)
        _enrich_semantic_object(obj, semantic_reads)
        _enrich_snapshot_object(obj, model_meta)

        if obj.primary_key == "TBD":
            col_set = {c.name for c in obj.columns}
            if "id" in col_set:
                obj.primary_key = "id"
            elif obj.name.startswith("snap_") and "dbt_scd_id" in col_set:
                obj.primary_key = "dbt_scd_id"
            elif obj.layer == "Semantic" or obj.name.startswith("vw_"):
                obj.primary_key = "-"

        if obj.layer == "Staging":
            if obj.name in _STAGING_ID_ONLY:
                col_set = {c.name for c in obj.columns}
                obj.business_key = (
                    "id, employee_code"
                    if obj.name == "stg_employees" and "employee_code" in col_set
                    else "id"
                )
            else:
                bk = _staging_business_key([c.name for c in obj.columns])
                if bk != "TBD":
                    obj.business_key = bk
        elif obj.layer == "Semantic" or obj.name.startswith("vw_"):
            if obj.business_key in ("TBD", "Consumer view (keys from underlying facts/marts)"):
                obj.business_key = _semantic_business_key([c.name for c in obj.columns])

        if obj.business_key == "TBD" or obj.business_key.startswith("source natural keys"):
            resolved = resolve_business_key(
                obj,
                dbt_unique_keys=dbt_unique_keys,
                model_meta=model_meta,
            )
            if resolved != "TBD":
                obj.business_key = resolved


def resolve_business_key(
    obj: ObjectInfo,
    *,
    dbt_unique_keys: dict[str, list[str]],
    model_meta: dict[str, Any],
) -> str:
    """Resolve business_key for one warehouse object (column-aware)."""
    override = _MODEL_BUSINESS_KEY_OVERRIDES.get(obj.name)
    if override:
        return override

    meta = model_meta.get(obj.name) or {}
    if meta.get("business_key"):
        return str(meta["business_key"])

    col_names = [c.name for c in obj.columns]
    col_set = set(col_names)

    if obj.layer == "Staging" or (
        obj.schema_name == "hr_raw"
        and (obj.name.startswith("stg_") or obj.name.startswith("raw_"))
    ):
        staging_bk = _staging_business_key(col_names)
        if staging_bk != "TBD":
            return staging_bk

    if obj.layer == "Semantic" or obj.name.startswith("vw_"):
        sem_bk = _semantic_business_key(col_names)
        if sem_bk != "Query grain (see view SQL)":
            return sem_bk

    if obj.name in dbt_unique_keys:
        filtered = _filter_business_key_columns(
            dbt_unique_keys[obj.name],
            layer=obj.layer,
            available=col_set,
        )
        if filtered:
            return ", ".join(filtered)

    natural = _natural_key_columns(col_names, obj.name, obj.layer)
    if natural:
        if obj.is_scd2 and "valid_from" in col_set and "valid_from" not in natural:
            return ", ".join(natural[:4] + ["valid_from"])
        return ", ".join(natural)

    hint = _grain_business_key_hint(obj.grain, col_names)
    if hint:
        return hint

    if obj.layer == "Semantic" or obj.name.startswith("vw_"):
        return "Consumer view (keys from underlying facts/marts)"

    if obj.layer == "Mart":
        return "Aggregate grain (see grain column)"

    if obj.schema_name == "hr_raw" and (obj.name.startswith("stg_") or obj.name.startswith("raw_")):
        if col_names:
            return "id" if "id" in col_set else "source columns (see field catalog)"
        return "source natural keys (DDL registered)"

    return "TBD"


def _infer_business_key(name: str) -> str:
    """Name-only fallback before columns are loaded."""
    if name in _MODEL_BUSINESS_KEY_OVERRIDES:
        return _MODEL_BUSINESS_KEY_OVERRIDES[name]
    if name.startswith("dim_employee"):
        return "source_emp_id / emp_no"
    if name.startswith("stg_") or name.startswith("raw_"):
        return "source natural keys (see source_* columns)"
    return "TBD"


def _column_flags(col_name: str) -> tuple[bool, bool]:
    lower = col_name.lower()
    if lower.endswith("_sk") or lower in ("id", "tenant_id", "source_system"):
        return False, False
    pii = any(p in lower for p in PII_COLUMN_PATTERNS)
    sensitive = any(p in lower for p in SENSITIVE_COLUMN_PATTERNS)
    return pii, sensitive


def _ai_aliases(col_name: str) -> list[str]:
    aliases: dict[str, list[str]] = {
        "emp_no": ["employee number", "employee code", "staff id"],
        "emp_fullname": ["employee name", "full name", "staff name"],
        "department_name": ["department", "dept", "org unit"],
        "designation_name": ["designation", "job title", "role"],
        "gross_salary": ["gross pay", "gross earnings"],
        "net_salary": ["net pay", "take home pay"],
        "remaining_days": ["leave balance", "balance days"],
        "approved_days": ["leave taken", "days on leave"],
    }
    return aliases.get(col_name, [])


def load_dbt_model_meta() -> dict[str, dict[str, Any]]:
    """Merge descriptions from dbt schema YAML files."""
    meta: dict[str, dict[str, Any]] = {}
    yml_paths = list(DBT_ROOT.rglob("*__models.yml")) + [
        DBT_ROOT / "models" / "schema.yml",
        DBT_ROOT / "seeds" / "_seeds.yml",
    ]
    for path in yml_paths:
        doc = _load_yaml(path)
        for model in doc.get("models") or []:
            name = str(model.get("name", ""))
            if not name:
                continue
            entry = meta.setdefault(name, {"description": "", "columns": {}})
            if model.get("description"):
                entry["description"] = str(model["description"]).strip()
            for col in model.get("columns") or []:
                cname = str(col.get("name", ""))
                if cname and col.get("description"):
                    entry["columns"][cname] = str(col["description"]).strip()
    return meta


def load_datamart_meta() -> dict[str, Any]:
    return _load_yaml(META_PATH)


def parse_staging_ddl() -> dict[str, list[tuple[str, str]]]:
    """Return stg_table -> [(column, pg_type)]."""
    if not STAGING_DDL_PATH.is_file():
        return {}
    content = STAGING_DDL_PATH.read_text(encoding="utf-8")
    tables: dict[str, list[tuple[str, str]]] = {}
    for block in re.findall(
        r'CREATE TABLE IF NOT EXISTS "\{schema\}"\.(\w+)\s*\((.*?)\)\s*"""',
        content,
        re.DOTALL,
    ):
        table = block[0]
        if not table.startswith("stg_") and not table.startswith("raw_"):
            continue
        cols: list[tuple[str, str]] = []
        for line in block[1].splitlines():
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(("PRIMARY", "UNIQUE", "CONSTRAINT")):
                continue
            parts = line.split()
            if len(parts) >= 2:
                cols.append((parts[0], parts[1]))
        tables[table] = cols
    return tables


def load_payroll_source_map() -> dict[str, str]:
    """dbt logical source name -> stg table."""
    doc = _load_yaml(SOURCES_PAYROLL_PATH)
    mapping: dict[str, str] = {}
    for src in doc.get("sources") or []:
        for tbl in src.get("tables") or []:
            logical = str(tbl.get("name", ""))
            physical = str(tbl.get("identifier") or logical)
            if logical:
                mapping[logical] = physical
    return mapping


def load_minthrm_table_map() -> dict[str, str]:
    doc = _load_yaml(MAPPING_PATH)
    return {str(k): str(v) for k, v in (doc.get("tables") or {}).items()}


def introspect_warehouse(engine: Engine) -> dict[tuple[str, str], ObjectInfo]:
    objects: dict[tuple[str, str], ObjectInfo] = {}
    sql = text(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema IN ('hr', 'hr_raw', 'hr_semantic', 'hr_snap')
          AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_schema, table_name
        """
    )
    col_sql = text(
        """
        SELECT column_name, data_type, is_nullable, column_default,
               character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
        for schema_name, table_name, table_type in rows:
            if schema_name == "hr" and table_name in WAREHOUSE_APP_TABLES:
                continue
            if any(table_name.endswith(s) for s in WAREHOUSE_EXCLUDE_SUFFIXES):
                continue
            if schema_name == "hr_raw" and not (
                table_name.startswith(STAGING_PREFIX) or table_name.startswith("raw_")
            ):
                continue
            layer = _infer_layer(table_name, schema_name)
            domain = _infer_domain(table_name)
            obj_type = "View" if table_type == "VIEW" or schema_name == "hr_semantic" else "Table"
            pk = _infer_pk(table_name, layer)
            obj = ObjectInfo(
                name=table_name,
                schema_name=schema_name,
                object_type=obj_type,
                layer=layer,
                domain=domain,
                primary_key=pk,
                business_key=_infer_business_key(table_name),
            )
            col_rows = conn.execute(
                col_sql, {"schema": schema_name, "table": table_name}
            ).fetchall()
            for cname, dtype, nullable, default, char_max, num_prec, num_scale in col_rows:
                pii, sensitive = _column_flags(cname)
                formatted_type = _format_pg_type(dtype, char_max, num_prec, num_scale)
                obj.columns.append(
                    ColumnInfo(
                        name=cname,
                        data_type=formatted_type,
                        is_nullable=(nullable == "YES"),
                        column_default=str(default) if default is not None else None,
                        pii=pii,
                        sensitive=sensitive,
                        ai_aliases=_ai_aliases(cname),
                    )
                )
                if pii:
                    obj.contains_pii = True
            scd_cols = {c.name for c in obj.columns}
            if {"is_current", "valid_from", "valid_to"}.issubset(scd_cols) or {
                "is_current",
                "effective_from",
                "effective_to",
            }.issubset(scd_cols):
                obj.is_scd2 = True
                obj.scd_type = "Type 2"
            objects[(schema_name, table_name)] = obj
    return objects


def enrich_objects(
    objects: dict[tuple[str, str], ObjectInfo],
    dbt_meta: dict[str, dict[str, Any]],
    er_meta: dict[str, Any],
    staging_ddl: dict[str, list[tuple[str, str]]],
    payroll_src: dict[str, str],
    minthrm_tables: dict[str, str],
) -> None:
    model_grains = er_meta.get("model_meta") or {}
    bronze = er_meta.get("bronze_lineage") or {}

    # Reverse payroll source map: stg -> logical MintHRM table names
    stg_to_logical: dict[str, str] = {}
    for logical, stg in payroll_src.items():
        stg_to_logical[stg] = logical

    logical_to_source: dict[str, str] = {}
    for key, physical in minthrm_tables.items():
        if key.startswith("payroll_") or key in ("prl_loan",):
            logical_to_source[key] = physical

    fact_sources: dict[str, list[str]] = {
        "fct_processed_salary": ["processed_sal_basic_data → stg_payroll_details"],
        "fct_processed_add_ded": ["processed_sal_add_ded → stg_payroll_add_ded"],
        "fct_processed_tax": ["processed_tax_data_for_employee → stg_payroll_tax"],
        "fct_processed_loan_deduction": [
            "processed_loan_data → stg_payroll_loan_deductions"
        ],
        "fct_salary_bank_instruction": [
            "prl_salary_retrieve → stg_payroll_salary_retrieve",
            "prl_salary_bank_data → stg_payroll_salary_bank_data",
        ],
        "fct_leave_application": ["hr_leaveapplication → stg_leave_requests"],
        "fct_leave_daily": ["hr_leaveapplication_dates → stg_leave_application_dates"],
        "fct_leave_balance_snapshot": ["hr_leave_balance → stg_leave_balance"],
        "fct_daily_attendance": ["HR_ATTEDANCE → stg_attendance"],
        "dim_employee": ["hr_empbasic → stg_employees → snap_employee"],
    }

    column_sources: dict[str, dict[str, str]] = {
        "fct_processed_salary": {
            "basic_salary": "processed_sal_basic_data.psb_basic_or_day_salary",
            "gross_salary": "processed_sal_basic_data.gross_salary_vw / psb_sub_total",
            "net_salary": "processed_sal_basic_data.psb_net_total",
            "tax_amount": "processed_sal_basic_data.psb_tax",
            "epf_employee_amount": "processed_sal_basic_data.psb_epf8",
            "epf_employer_amount": "processed_sal_basic_data.psb_epf12",
            "etf_amount": "processed_sal_basic_data.psb_epf3",
            "employee_sk": "dim_employee via source_emp_id",
            "payroll_period_sk": "dim_payroll_period via year/month/half",
            "payroll_group_sk": "dim_payroll_group via source_payroll_group_id",
            "process_status": "processed_sal_basic_data.process_status",
            "tenant_id": "ETL tenant_id var",
            "_loaded_at": "ETL load timestamp",
        },
        "dim_employee": {
            "emp_no": "hr_empbasic.emp_no",
            "emp_fullname": "hr_empbasic.emp_fullname",
            "department_name": "company_hierarchy / designation",
            "basic_salary": "hr_empbasic.basicsalary",
            "date_of_birth": "hr_empbasic.emp_dob",
            "nic": "hr_empbasic.emp_nic",
        },
    }

    for (_schema, name), obj in objects.items():
        dbt = dbt_meta.get(name) or {}
        if dbt.get("description"):
            obj.description = dbt["description"]
        grain = (model_grains.get(name) or {}).get("grain")
        if grain:
            obj.grain = str(grain)

        for col in obj.columns:
            if col.name in (dbt.get("columns") or {}):
                col.description = dbt["columns"][col.name]
            src_map = column_sources.get(name) or {}
            if col.name in src_map:
                col.source_column = src_map[col.name]
                col.transformation = "ETL extract + dbt conformed join"

        if name in fact_sources:
            obj.source_systems = fact_sources[name]
        elif name in bronze:
            obj.source_systems = list(bronze[name])
        elif obj.schema_name == "hr_raw" and name in stg_to_logical:
            logical = stg_to_logical[name]
            obj.source_systems = [logical]
        elif name == "stg_employees":
            obj.source_systems = ["hr_empbasic", "hr_employment", "hr_empcontact"]
        elif name == "stg_leave_requests":
            obj.source_systems = ["hr_leaveapplication"]
        elif name == "stg_leave_application_dates":
            obj.source_systems = ["hr_leaveapplication_dates"]
        elif name == "stg_leave_types":
            obj.source_systems = ["hr_leavetype"]
        elif name == "stg_leave_balance":
            obj.source_systems = ["hr_leave_balance"]
        elif name == "stg_leave_entitlement":
            obj.source_systems = ["prl_leaveentitle"]
        elif name == "stg_leave_approvals":
            obj.source_systems = ["hr_leaveapplication_superiors"]
        elif name == "stg_leave_reason":
            obj.source_systems = ["hr_predefine_leave_purpose"]
        elif name == "stg_short_leave":
            obj.source_systems = ["hr_short_leave"]
        elif name == "stg_attendance":
            obj.source_systems = ["HR_ATTEDANCE"]
        elif name == "raw_hr_payroll_groups":
            obj.source_systems = ["hr_payroll_groups"]
        elif name.startswith("stg_payroll"):
            for key, physical in minthrm_tables.items():
                if key.startswith("payroll") and payroll_src.get(physical) == name:
                    obj.source_systems = [physical]
                    break
            if not obj.source_systems:
                obj.source_systems = ["MintHRM payroll engine tables — TBD"]
        elif obj.schema_name == "hr_raw" and name.startswith("stg_"):
            if not obj.source_systems:
                obj.source_systems = ["MintHRM source — register extractor mapping"]

        if obj.schema_name == "hr_raw" and name in staging_ddl and not name.startswith("stg_"):
            ddl_cols = {c[0]: c[1] for c in staging_ddl[name]}
            for col in obj.columns:
                if col.name in ddl_cols and col.data_type == "TBD":
                    col.data_type = ddl_cols[col.name]


def discover_dbt_only_objects(objects: dict[tuple[str, str], ObjectInfo]) -> None:
    """Add documented dbt models not yet materialized in warehouse."""
    existing = {name for (_s, name) in objects}
    mart_dirs = [
        DBT_ROOT / "models" / "marts" / "employment",
        DBT_ROOT / "models" / "marts" / "payroll",
        DBT_ROOT / "models" / "marts" / "leave",
        DBT_ROOT / "models" / "marts",
        DBT_ROOT / "models" / "semantic",
        DBT_ROOT / "snapshots",
    ]
    for d in mart_dirs:
        if not d.is_dir():
            continue
        for sql in d.glob("*.sql"):
            name = sql.stem
            if name in existing:
                continue
            schema = "hr_semantic" if name.startswith("vw_") else "hr"
            layer = _infer_layer(name, schema)
            objects[(schema, name)] = ObjectInfo(
                name=name,
                schema_name=schema,
                object_type="View" if name.startswith("vw_") else "Table",
                layer=layer,
                domain=_infer_domain(name),
                primary_key=_infer_pk(name, layer),
                business_key=_infer_business_key(name),
                description="Documented in dbt; not materialized in warehouse at generation time.",
            )


def render_table_doc(obj: ObjectInfo, dbt_meta: dict[str, dict[str, Any]]) -> str:
    dbt = dbt_meta.get(obj.name) or {}
    desc = obj.description or dbt.get("description") or "TBD"
    gov = DOMAIN_GOVERNANCE.get(obj.domain, DEFAULT_GOVERNANCE)
    lines = [
        f"# {obj.name}",
        "",
        "## Overview",
        "",
        f"**Business Purpose:**  ",
        desc.replace("\n", " "),
        "",
        f"**Schema:** `{obj.schema_name}`  ",
        f"**Object Type:** {obj.object_type}  ",
        f"**Layer:** {obj.layer}  ",
        f"**Domain:** {obj.domain}  ",
        f"**Grain:** {obj.grain}  ",
        f"**Primary Key:** {obj.primary_key}  ",
        f"**Business Key:** {obj.business_key}  ",
        f"**SCD Type:** {obj.scd_type}  ",
        f"**Refresh Type:** {obj.refresh_type}  ",
        f"**Refresh Frequency:** {obj.refresh_frequency}  ",
        "",
        "**Source Systems:**",
    ]
    if obj.source_systems:
        lines.extend(f"- {s}" for s in obj.source_systems)
    else:
        lines.append("- TBD")
    lines.extend(
        [
            "",
            "**Consumers:**",
            *[f"- {c}" for c in obj.consumers],
            "",
            "## Governance",
            "",
            f"| Property | Value |",
            f"|----------|-------|",
            f"| Data Owner | {gov['data_owner']} |",
            f"| Technical Owner | {gov['technical_owner']} |",
            f"| Classification | {gov['classification']} |",
            f"| Contains PII | {'Yes' if obj.contains_pii else 'No'} |",
            f"| Retention | {gov['retention']} |",
            "",
        ]
    )
    if obj.is_scd2:
        lines.extend(
            [
                "## SCD Type 2",
                "",
                "**Dimension Type:** Type 2  ",
                "**Current Row Logic:** `is_current = true`  ",
                "**History Logic:** `valid_from` / `valid_to` (or `effective_from` / `effective_to`)  ",
                "",
            ]
        )
    lines.extend(
        [
            "## Columns",
            "",
            "| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |",
            "|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|",
        ]
    )
    if obj.columns:
        for col in obj.columns:
            aliases = ", ".join(col.ai_aliases) if col.ai_aliases else "TBD"
            default = col.column_default or "-"
            lines.append(
                f"| `{col.name}` | {col.data_type} | "
                f"{'Yes' if col.is_nullable else 'No'} | {default} | "
                f"{col.description} | {col.source_column} | {col.transformation} | "
                f"{'Yes' if col.pii else 'No'} | {'Yes' if col.sensitive else 'No'} | {aliases} |"
            )
    else:
        lines.append("| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |")
    lines.append("")
    return "\n".join(lines)


def render_semantic_doc(view_name: str, obj: ObjectInfo | None, reads: str) -> str:
    ai = AI_VIEW_METADATA.get(view_name, {})
    aliases = ai.get("aliases") or ["TBD"]
    questions = ai.get("questions") or ["TBD"]
    dimensions = ai.get("dimensions") or ["TBD"]
    measures = ai.get("measures") or ["TBD"]
    purpose = (obj.description if obj else None) or f"Semantic reporting view. Reads: {reads}"
    lines = [
        f"# sv_{view_name}",
        "",
        f"> Warehouse object: `{view_name}` in schema `hr_semantic`",
        "",
        "## Overview",
        "",
        f"**Purpose:** {purpose}",
        "",
        f"**Entity:** {_infer_domain(view_name)}  ",
        "**Grain:** One row per business grain of underlying mart/fact — TBD per query  ",
        "**Recommended Usage:** Reporting and AI queries (query `hr_semantic` only)  ",
        "",
        f"**Upstream reads:** {reads or 'TBD'}",
        "",
        "## Recommended Filters",
        "",
        "- `department_name` / `legal_entity` — org slice",
        "- Period columns (`year_month`, `period_label`, `snapshot_month`) — time slice",
        "- `is_current = true` on joined dimensions when applicable",
        "",
        "## Join Dependencies",
        "",
        f"- {reads or 'TBD'}",
        "",
        "## AI Agent Metadata",
        "",
        "**Natural Language Aliases:**",
        *[f"- {a}" for a in aliases],
        "",
        "**Typical Questions:**",
        *[f"- {q}" for q in questions],
        "",
        "**Recommended Dimensions:**",
        *[f"- {d}" for d in dimensions],
        "",
        "**Recommended Measures:**",
        *[f"- {m}" for m in measures],
        "",
    ]
    if obj and obj.columns:
        lines.extend(["## Exposed Columns", ""])
        for col in obj.columns[:40]:
            lines.append(f"- `{col.name}` ({col.data_type})")
        if len(obj.columns) > 40:
            lines.append(f"- … and {len(obj.columns) - 40} more columns")
        lines.append("")
    return "\n".join(lines)


def render_warehouse_catalog(objects: list[ObjectInfo], generated_at: str) -> str:
    lines = [
        "# Warehouse Catalog",
        "",
        "MintHRM Enterprise Data Warehouse — object inventory.",
        "",
        f"**Generated:** {generated_at}  ",
        "**Owner:** Data Engineering  ",
        "",
        "| Object | Schema | Type | Domain | Layer | Refresh | Description |",
        "|--------|--------|------|--------|-------|---------|-------------|",
    ]
    for obj in sorted(objects, key=lambda o: (o.layer, o.schema_name, o.name)):
        desc = (obj.description or "TBD").replace("\n", " ").replace("|", "/")[:120]
        lines.append(
            f"| `{obj.name}` | `{obj.schema_name}` | {obj.object_type} | "
            f"{obj.domain} | {obj.layer} | {obj.refresh_frequency} | {desc} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_glossary() -> str:
    lines = ["# Business Glossary", "", "Independent business terms for MintHRM analytics.", ""]
    for item in GLOSSARY:
        lines.extend(
            [
                f"## {item['term']}",
                "",
                f"**Definition:** {item['definition']}  ",
                f"**Formula:** {item['formula']}  ",
                f"**Owner:** {item['owner']}  ",
                "",
            ]
        )
    return "\n".join(lines)


def render_metrics() -> str:
    lines = ["# Metrics Dictionary", "", "Standard HR analytics metrics.", ""]
    for m in METRICS:
        lines.extend(
            [
                f"## {m['metric']}",
                "",
                f"**Description:** {m['description']}  ",
                f"**Formula:** {m['formula']}  ",
                f"**Filters:** {m['filters']}  ",
                f"**Source:** `{m['source']}`  ",
                f"**Aggregation:** {m['aggregation']}  ",
                f"**Business Owner:** {m['business_owner']}  ",
                "",
            ]
        )
    return "\n".join(lines)


def render_data_quality() -> str:
    lines = [
        "# Data Quality Rules",
        "",
        "Validation rules for warehouse objects (dbt tests + design rules).",
        "",
    ]
    for rule in DATA_QUALITY_RULES:
        lines.extend(
            [
                f"## {rule['rule']}",
                "",
                f"**Scope:** `{rule['scope']}`  ",
                f"**Validation:** `{rule['validation']}`  ",
                "",
            ]
        )
    return "\n".join(lines)


def _lineage_section(title: str, chains: list[list[str]]) -> list[str]:
    lines = [f"## {title}", ""]
    for chain in chains:
        lines.append("```text")
        lines.extend(f"{step}" if i == 0 else f"  ↓\n{step}" for i, step in enumerate(chain))
        lines.append("```")
        lines.append("")
    return lines


def render_lineage_employee() -> str:
    chains = [
        [
            "hr_empbasic.emp_id",
            "stg_employees.id",
            "snap_employee (dbt snapshot)",
            "dim_employee.employee_sk",
            "mart_employee_current",
            "vw_headcount (semantic)",
        ],
        [
            "hr_employment.ref_emp_id",
            "stg_employees (enriched attributes)",
            "fct_employment_snapshot",
            "mart_headcount_monthly",
        ],
        [
            "hr_lifecycle",
            "stg_lifecycle",
            "fct_lifecycle_event",
            "vw_lifecycle_summary / vw_turnover",
        ],
    ]
    lines = ["# Employee Lineage", "", "Source-to-target mapping for workforce domain.", ""]
    lines.extend(_lineage_section("Core employee master", chains))
    return "\n".join(lines)


def render_lineage_payroll(payroll_src: dict[str, str]) -> str:
    lines = ["# Payroll Lineage", "", "MintHRM processed payroll → warehouse marts.", ""]
    core = [
        [
            "processed_sal_basic_data",
            "stg_payroll_details",
            "stg_processed_sal_basic_data (dbt view)",
            "fct_processed_salary",
            "mart_processed_payroll_summary",
            "vw_payroll_summary",
        ],
        [
            "processed_sal_add_ded",
            "stg_payroll_add_ded",
            "fct_processed_add_ded",
            "mart_horizontal_paysheet_dynamic",
        ],
        [
            "processed_tax_data_for_employee",
            "stg_payroll_tax",
            "fct_processed_tax",
            "mart_statutory_summary",
        ],
        [
            "prl_salary_retrieve + prl_salary_bank_data",
            "stg_payroll_salary_retrieve / stg_payroll_salary_bank_data",
            "fct_salary_bank_instruction",
        ],
    ]
    lines.extend(_lineage_section("Processed payroll facts", core))
    lines.extend(["## Source alias map (dbt)", ""])
    lines.append("| MintHRM logical name | hr_raw staging |")
    lines.append("|----------------------|----------------|")
    for logical, stg in sorted(payroll_src.items()):
        lines.append(f"| `{logical}` | `{stg}` |")
    lines.append("")
    return "\n".join(lines)


def render_lineage_leave() -> str:
    chains = [
        [
            "hr_leaveapplication",
            "stg_leave_requests",
            "int_leave_application",
            "fct_leave_application",
            "vw_employee_leave_history",
        ],
        [
            "hr_leaveapplication_dates",
            "stg_leave_application_dates",
            "fct_leave_daily",
            "mart_leave_monthly_summary",
        ],
        [
            "hr_leave_balance",
            "stg_leave_balance",
            "fct_leave_balance_snapshot",
            "vw_current_leave_balance / vw_leave_liability",
        ],
        [
            "hr_leaveapplication_superiors",
            "stg_leave_approvals",
            "fct_leave_approval",
            "vw_pending_leave_approvals",
        ],
    ]
    lines = ["# Leave Lineage", "", "Leave intelligence mart source-to-target paths.", ""]
    lines.extend(_lineage_section("Leave modules", chains))
    return "\n".join(lines)


def render_lineage_attendance() -> str:
    chains = [
        [
            "HR_ATTEDANCE / hr_attedance",
            "stg_attendance",
            "fct_daily_attendance",
            "mart_attendance_monthly_summary",
            "vw_attendance_summary",
        ],
        [
            "fct_daily_attendance (OT derivation)",
            "fct_overtime",
            "mart_attendance_monthly_summary.total_overtime_hours",
        ],
    ]
    lines = ["# Attendance Lineage", "", "Attendance and overtime analytics path.", ""]
    lines.extend(_lineage_section("Daily attendance", chains))
    return "\n".join(lines)


def write_docs(
    objects: dict[tuple[str, str], ObjectInfo],
    dbt_meta: dict[str, dict[str, Any]],
    er_meta: dict[str, Any],
    payroll_src: dict[str, str],
    tenant_id: str,
) -> dict[str, int]:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    counts = {"tables": 0, "semantic": 0, "lineage": 0, "top": 0}

    tables_dir = DOCS_ROOT / "tables"
    semantic_dir = DOCS_ROOT / "semantic"
    lineage_dir = DOCS_ROOT / "lineage"
    for d in (tables_dir, semantic_dir, lineage_dir):
        d.mkdir(parents=True, exist_ok=True)

    obj_list = list(objects.values())
    (DOCS_ROOT / "warehouse_catalog.md").write_text(
        render_warehouse_catalog(obj_list, generated_at), encoding="utf-8"
    )
    counts["top"] += 1
    (DOCS_ROOT / "business_glossary.md").write_text(render_glossary(), encoding="utf-8")
    counts["top"] += 1
    (DOCS_ROOT / "metrics_dictionary.md").write_text(render_metrics(), encoding="utf-8")
    counts["top"] += 1
    (DOCS_ROOT / "data_quality_rules.md").write_text(render_data_quality(), encoding="utf-8")
    counts["top"] += 1

    table_prefixes = ("dim_", "fct_", "fact_", "snap_", "mart_", "ref_")
    for obj in obj_list:
        if obj.layer == "Semantic":
            continue
        if obj.name.startswith("stg_") or obj.schema_name == "hr_raw":
            continue
        if not obj.name.startswith(table_prefixes):
            continue
        fname = obj.name
        if obj.name == "dim_canonical_pay_item":
            fname = "ref_canonical_pay_item"
        path = tables_dir / f"{fname}.md"
        path.write_text(render_table_doc(obj, dbt_meta), encoding="utf-8")
        counts["tables"] += 1

    semantic_reads = {
        str(v["name"]): str(v.get("reads", "TBD")) for v in (er_meta.get("semantic_views") or [])
    }
    for view_name, reads in semantic_reads.items():
        obj = objects.get(("hr_semantic", view_name))
        path = semantic_dir / f"sv_{view_name}.md"
        path.write_text(render_semantic_doc(view_name, obj, reads), encoding="utf-8")
        counts["semantic"] += 1

    # Also document semantic views discovered only in dbt
    for (_schema, name), obj in objects.items():
        if not name.startswith("vw_"):
            continue
        path = semantic_dir / f"sv_{name}.md"
        if path.exists():
            continue
        path.write_text(
            render_semantic_doc(name, obj, semantic_reads.get(name, "TBD")),
            encoding="utf-8",
        )
        counts["semantic"] += 1

    (lineage_dir / "employee_lineage.md").write_text(render_lineage_employee(), encoding="utf-8")
    (lineage_dir / "payroll_lineage.md").write_text(
        render_lineage_payroll(payroll_src), encoding="utf-8"
    )
    (lineage_dir / "leave_lineage.md").write_text(render_lineage_leave(), encoding="utf-8")
    (lineage_dir / "attendance_lineage.md").write_text(render_lineage_attendance(), encoding="utf-8")
    counts["lineage"] = 4

    readme = DOCS_ROOT / "DATA_DICTIONARY.md"
    readme.write_text(
        "\n".join(
            [
                "# MintHRM Data Dictionary",
                "",
                f"Generated from warehouse schema (`{tenant_id}`) and dbt metadata.",
                "",
                f"**Last generated:** {generated_at}  ",
                "",
                "## Regenerate",
                "",
                "```powershell",
                "cd backend",
                "$env:PYTHONPATH=\".\"",
                "python tools/generate_data_dictionary.py --tenant demo_tenant",
                "```",
                "",
                "## Contents",
                "",
                "| Document | Purpose |",
                "|----------|---------|",
                "| [warehouse_catalog.md](warehouse_catalog.md) | Full object inventory |",
                "| [business_glossary.md](business_glossary.md) | Business terms |",
                "| [metrics_dictionary.md](metrics_dictionary.md) | KPI definitions |",
                "| [data_quality_rules.md](data_quality_rules.md) | Validation rules |",
                "| [tables/](tables/) | Table-level documentation |",
                "| [semantic/](semantic/) | Semantic view (`vw_*`) documentation |",
                "| [lineage/](lineage/) | Source-to-target lineage by domain |",
                "",
                "## Warehouse tables (SQL)",
                "",
                "Field-level catalog is also stored in the tenant warehouse:",
                "",
                "| Object | Schema | Purpose |",
                "|--------|--------|---------|",
                "| `data_dictionary_object` | `hr_control` | Table/view inventory |",
                "| `data_dictionary_field` | `hr_control` | Column catalog (Field, Type, Nullable, PK, FK, Description, Source) |",
                "| `vw_data_dictionary` | `hr_semantic` | Query-ready dictionary view |",
                "",
                "```sql",
                "SELECT field_name, data_type, nullable, pk, fk, description, source",
                "FROM hr_semantic.vw_data_dictionary",
                "WHERE object_name = 'fct_processed_salary'",
                "ORDER BY ordinal_position;",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    counts["top"] += 1
    return counts


def discover_staging_from_ddl(
    objects: dict[tuple[str, str], ObjectInfo],
    staging_ddl: dict[str, list[tuple[str, str]]],
    raw_schema: str = "hr_raw",
) -> None:
    """Add staging tables defined in DDL that are not yet in information_schema."""
    existing = {(s, n) for (s, n) in objects}
    for table_name, cols in staging_ddl.items():
        key = (raw_schema, table_name)
        if key in existing:
            continue
        obj = ObjectInfo(
            name=table_name,
            schema_name=raw_schema,
            object_type="Table",
            layer="Staging",
            domain=_infer_domain(table_name),
            primary_key="id",
            business_key="source natural keys (see source_* columns)",
            description="Bronze staging table (DDL registered; awaiting first ETL load).",
        )
        for col_name, col_type in cols:
            pii, sensitive = _column_flags(col_name)
            obj.columns.append(
                ColumnInfo(
                    name=col_name,
                    data_type=col_type,
                    is_nullable=True,
                    description="TBD",
                    source_column="MintHRM source via ETL",
                    pii=pii,
                    sensitive=sensitive,
                )
            )
            if pii:
                obj.contains_pii = True
        objects[key] = obj


def build_catalog(
    engine: Engine,
    tenant_id: str,
) -> tuple[dict[tuple[str, str], ObjectInfo], dict[str, dict[str, Any]], dict[str, Any]]:
    """Introspect warehouse + enrich metadata (shared by markdown export and DB sync)."""
    dbt_meta = load_dbt_model_meta()
    er_meta = load_datamart_meta()
    staging_ddl = parse_staging_ddl()
    payroll_src = load_payroll_source_map()
    minthrm_tables = load_minthrm_table_map()

    objects = introspect_warehouse(engine)
    discover_staging_from_ddl(objects, staging_ddl)
    discover_dbt_only_objects(objects)
    enrich_objects(objects, dbt_meta, er_meta, staging_ddl, payroll_src, minthrm_tables)
    finalize_object_metadata(objects, er_meta, payroll_src=payroll_src, dbt_meta=dbt_meta)
    return objects, dbt_meta, er_meta


def generate(tenant_id: str, *, sync_warehouse: bool = True) -> dict[str, int]:
    engine = get_warehouse_engine_sync(tenant_id)
    objects, dbt_meta, er_meta = build_catalog(engine, tenant_id)
    payroll_src = load_payroll_source_map()
    counts = write_docs(objects, dbt_meta, er_meta, payroll_src, tenant_id)
    if sync_warehouse:
        wh = sync_warehouse_dictionary(engine, tenant_id, objects, er_meta)
        counts["warehouse_objects"] = wh["warehouse_objects"]
        counts["warehouse_fields"] = wh["warehouse_fields"]
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MintHRM data dictionary")
    parser.add_argument("--tenant", default="demo_tenant", help="Warehouse tenant id")
    parser.add_argument(
        "--no-warehouse",
        action="store_true",
        help="Skip syncing hr_control data dictionary tables",
    )
    args = parser.parse_args(argv)
    counts = generate(args.tenant, sync_warehouse=not args.no_warehouse)
    msg = (
        f"OK data dictionary for {args.tenant}: "
        f"{counts['top']} index files, {counts['tables']} tables, "
        f"{counts['semantic']} semantic views, {counts['lineage']} lineage docs"
    )
    if counts.get("warehouse_fields"):
        msg += (
            f", {counts['warehouse_objects']} warehouse objects, "
            f"{counts['warehouse_fields']} warehouse fields"
        )
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
