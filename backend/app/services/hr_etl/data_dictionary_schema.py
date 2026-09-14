"""Warehouse-resident data dictionary tables (hr_control) + semantic catalog view."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.services.hr_etl.schema_names import control_schema, semantic_schema

logger = logging.getLogger("hr_etl.data_dictionary")


def data_dictionary_ddl(ctrl: str) -> list[str]:
    return [
        f"""
        CREATE TABLE IF NOT EXISTS "{ctrl}".data_dictionary_object (
            object_id SERIAL PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL,
            schema_name VARCHAR(64) NOT NULL,
            object_name VARCHAR(128) NOT NULL,
            object_type VARCHAR(32) NOT NULL,
            layer VARCHAR(32) NOT NULL,
            domain VARCHAR(64) NOT NULL,
            grain TEXT,
            description TEXT,
            primary_key VARCHAR(128),
            business_key VARCHAR(128),
            refresh_frequency VARCHAR(32) DEFAULT 'Daily',
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, schema_name, object_name)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS "{ctrl}".data_dictionary_field (
            field_id SERIAL PRIMARY KEY,
            object_id INTEGER NOT NULL
                REFERENCES "{ctrl}".data_dictionary_object(object_id) ON DELETE CASCADE,
            ordinal_position INTEGER NOT NULL DEFAULT 0,
            field_name VARCHAR(128) NOT NULL,
            data_type VARCHAR(128) NOT NULL,
            is_nullable BOOLEAN NOT NULL DEFAULT TRUE,
            is_primary_key BOOLEAN NOT NULL DEFAULT FALSE,
            foreign_key_target VARCHAR(128),
            description TEXT,
            source_system TEXT,
            pii BOOLEAN NOT NULL DEFAULT FALSE,
            sensitive BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE (object_id, field_name)
        )
        """,
        f'CREATE INDEX IF NOT EXISTS idx_dd_field_object ON "{ctrl}".data_dictionary_field (object_id)',
        f'CREATE INDEX IF NOT EXISTS idx_dd_object_tenant ON "{ctrl}".data_dictionary_object (tenant_id, object_name)',
    ]


def ensure_data_dictionary_tables(conn: Connection, tenant_id: str) -> None:
    ctrl = control_schema(tenant_id)
    for ddl in data_dictionary_ddl(ctrl):
        conn.execute(text(ddl))


def build_fk_map(er_meta: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Map (table_name, column_name) -> referenced dimension/fact table."""
    fk: dict[tuple[str, str], str] = {}
    relationships = er_meta.get("relationships") or {}
    for _domain, rels in relationships.items():
        if not isinstance(rels, list):
            continue
        for rel in rels:
            from_table = str(rel.get("from", ""))
            to_table = str(rel.get("to", ""))
            label = str(rel.get("label", ""))
            if not from_table or not to_table or not label.endswith("_sk"):
                continue
            fk[(from_table, label)] = to_table
    return fk


def _format_pg_type(
    data_type: str,
    char_max: int | None,
    num_precision: int | None,
    num_scale: int | None,
) -> str:
    dt = (data_type or "text").lower()
    if dt in ("character varying", "varchar"):
        return f"varchar({char_max or 255})"
    if dt in ("character", "char"):
        return f"char({char_max or 1})"
    if dt == "numeric":
        if num_precision:
            return f"numeric({num_precision},{num_scale or 0})"
        return "numeric"
    if dt == "double precision":
        return "double precision"
    if dt == "real":
        return "real"
    if dt == "integer":
        return "integer"
    if dt == "bigint":
        return "bigint"
    if dt == "smallint":
        return "smallint"
    if dt == "boolean":
        return "boolean"
    if dt == "date":
        return "date"
    if dt == "text":
        return "text"
    if "timestamp" in dt:
        return "timestamp"
    if dt == "jsonb":
        return "jsonb"
    return data_type


def _resolve_source(col_name: str, source_column: str, is_pk: bool, fk_target: str | None) -> str:
    if source_column and source_column != "TBD":
        return source_column
    if col_name == "tenant_id":
        return "CDC metadata"
    if col_name in ("_loaded_at", "_refreshed_at", "extracted_at"):
        return "ETL"
    if is_pk and col_name.endswith("_sk"):
        return "Generated"
    if fk_target:
        return fk_target
    return "TBD"


def _field_description(col_name: str, description: str, obj_name: str) -> str:
    if description and description != "TBD":
        return description
    defaults: dict[tuple[str, str], str] = {
        ("fct_processed_salary", "processed_salary_sk"): "Surrogate key",
        ("fct_processed_salary", "employee_sk"): "Employee surrogate key",
        ("fct_processed_salary", "payroll_period_sk"): "Payroll period key",
        ("fct_processed_salary", "payroll_group_sk"): "Payroll group key",
        ("fct_processed_salary", "gross_salary"): "Final processed gross salary",
        ("fct_processed_salary", "net_salary"): "Final net salary payable",
        ("fct_processed_salary", "process_status"): "processed / reversed",
        ("fct_processed_salary", "tenant_id"): "Tenant isolation key",
        ("fct_processed_salary", "_loaded_at"): "Warehouse load timestamp",
        ("fct_processed_salary", "basic_salary"): "Processed basic salary component",
        ("fct_processed_salary", "tax_amount"): "Processed tax deduction amount",
        ("fct_processed_salary", "total_deductions"): "Total deductions after gross",
    }
    return defaults.get((obj_name, col_name), "TBD")


def _is_primary_key_column(col_name: str, obj: Any) -> bool:
    pk = (obj.primary_key or "").strip()
    if pk and pk != "TBD" and col_name == pk:
        return True
    if col_name == "id" and obj.name.startswith("fact_"):
        return True
    expected = f"{obj.name[4:]}_sk" if obj.name.startswith("fct_") else ""
    if expected and col_name == expected:
        return True
    return False


def sync_warehouse_dictionary(
    engine: Engine,
    tenant_id: str,
    objects: dict[tuple[str, str], Any],
    er_meta: dict[str, Any],
) -> dict[str, int]:
    """Replace tenant dictionary rows and refresh hr_semantic.vw_data_dictionary."""
    ctrl = control_schema(tenant_id)
    semantic = semantic_schema(tenant_id)
    fk_map = build_fk_map(er_meta)
    generated_at = datetime.now(timezone.utc)

    table_prefixes = ("dim_", "fct_", "fact_", "snap_", "mart_", "stg_", "raw_")
    object_rows: list[Any] = []
    for obj in objects.values():
        if any(obj.name.endswith(s) for s in ("__dbt_test", "__dbt_tmp")):
            continue
        if obj.name in {"database_connections", "data_access_rules"}:
            continue
        if obj.schema_name == "hr_raw":
            if obj.name.startswith("stg_") or obj.name.startswith("raw_"):
                object_rows.append(obj)
            continue
        if obj.layer == "Semantic" or obj.name.startswith("vw_"):
            object_rows.append(obj)
            continue
        if obj.name.startswith(table_prefixes):
            object_rows.append(obj)

    if not object_rows:
        logger.warning(
            "Data dictionary sync aborted for tenant=%s: no warehouse objects discovered "
            "(existing catalog rows left unchanged). Check warehouse connection and schemas.",
            tenant_id,
        )
        return {
            "warehouse_objects": 0,
            "warehouse_fields": 0,
            "skipped": True,
            "reason": "no_objects_discovered",
        }

    field_count = 0
    with engine.begin() as conn:
        ensure_data_dictionary_tables(conn, tenant_id)
        conn.execute(
            text(f'DELETE FROM "{ctrl}".data_dictionary_field WHERE object_id IN '
                 f'(SELECT object_id FROM "{ctrl}".data_dictionary_object WHERE tenant_id = :tid)'),
            {"tid": tenant_id},
        )
        conn.execute(
            text(f'DELETE FROM "{ctrl}".data_dictionary_object WHERE tenant_id = :tid'),
            {"tid": tenant_id},
        )

        for obj in sorted(object_rows, key=lambda o: (o.schema_name, o.name)):
            row = conn.execute(
                text(
                    f'INSERT INTO "{ctrl}".data_dictionary_object '
                    "(tenant_id, schema_name, object_name, object_type, layer, domain, "
                    "grain, description, primary_key, business_key, refresh_frequency, generated_at) "
                    "VALUES (:tenant_id, :schema_name, :object_name, :object_type, :layer, :domain, "
                    ":grain, :description, :primary_key, :business_key, :refresh_frequency, :generated_at) "
                    "RETURNING object_id"
                ),
                {
                    "tenant_id": tenant_id,
                    "schema_name": obj.schema_name,
                    "object_name": obj.name,
                    "object_type": obj.object_type,
                    "layer": obj.layer,
                    "domain": obj.domain,
                    "grain": obj.grain,
                    "description": obj.description,
                    "primary_key": obj.primary_key,
                    "business_key": obj.business_key,
                    "refresh_frequency": obj.refresh_frequency,
                    "generated_at": generated_at,
                },
            ).fetchone()
            object_id = row[0]

            for ordinal, col in enumerate(obj.columns, start=1):
                fk_target = fk_map.get((obj.name, col.name))
                if not fk_target and col.name.endswith("_sk") and not _is_primary_key_column(col.name, obj):
                    guess = col.name[: -len("_sk")]
                    if guess.startswith("dim_") or guess in ("employee", "payroll_period", "payroll_group"):
                        fk_target = guess if guess.startswith("dim_") else f"dim_{guess}"
                is_pk = _is_primary_key_column(col.name, obj)
                description = _field_description(col.name, col.description, obj.name)
                source = _resolve_source(col.name, col.source_column, is_pk, fk_target)
                conn.execute(
                    text(
                        f'INSERT INTO "{ctrl}".data_dictionary_field '
                        "(object_id, ordinal_position, field_name, data_type, is_nullable, "
                        "is_primary_key, foreign_key_target, description, source_system, pii, sensitive) "
                        "VALUES (:object_id, :ordinal_position, :field_name, :data_type, :is_nullable, "
                        ":is_primary_key, :foreign_key_target, :description, :source_system, :pii, :sensitive)"
                    ),
                    {
                        "object_id": object_id,
                        "ordinal_position": ordinal,
                        "field_name": col.name,
                        "data_type": col.data_type,
                        "is_nullable": col.is_nullable,
                        "is_primary_key": is_pk,
                        "foreign_key_target": fk_target,
                        "description": description,
                        "source_system": source,
                        "pii": col.pii,
                        "sensitive": col.sensitive,
                    },
                )
                field_count += 1

        conn.execute(
            text(f'CREATE OR REPLACE VIEW "{semantic}".vw_data_dictionary AS '
                 f'SELECT '
                 f'  o.tenant_id, '
                 f'  o.schema_name, '
                 f'  o.object_name, '
                 f'  o.object_type, '
                 f'  o.layer, '
                 f'  o.domain, '
                 f'  o.grain AS object_grain, '
                 f'  o.description AS object_description, '
                 f'  f.ordinal_position, '
                 f'  f.field_name, '
                 f'  f.data_type, '
                 f"  CASE WHEN f.is_nullable THEN 'YES' ELSE 'NO' END AS nullable, "
                 f"  CASE WHEN f.is_primary_key THEN 'YES' ELSE '' END AS pk, "
                 f'  COALESCE(f.foreign_key_target, \'\') AS fk, '
                 f'  f.description, '
                 f'  f.source_system AS source, '
                 f'  f.pii, '
                 f'  f.sensitive, '
                 f'  o.generated_at AS dictionary_generated_at '
                 f'FROM "{ctrl}".data_dictionary_object o '
                 f'JOIN "{ctrl}".data_dictionary_field f ON f.object_id = o.object_id')
        )

    return {"warehouse_objects": len(object_rows), "warehouse_fields": field_count}
