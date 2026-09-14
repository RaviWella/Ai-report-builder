"""
Maintain semantic_catalog.yaml against the live warehouse.

Commands
--------
  validate          Fail if catalog references missing tables/columns (CI-friendly).
  refresh           Merge warehouse changes into the catalog (dry-run by default).
  report            JSON snapshot: drift, warehouse-only tables, stale refs.

Usage (from backend/):
  PYTHONPATH=. python tools/semantic_catalog_tool.py validate
  PYTHONPATH=. python tools/semantic_catalog_tool.py refresh --dry-run
  PYTHONPATH=. python tools/semantic_catalog_tool.py refresh --write
  PYTHONPATH=. python tools/semantic_catalog_tool.py report --json drift.json

Per-tenant ETL warehouse (Phase 11):
  PYTHONPATH=. python tools/semantic_catalog_tool.py refresh --tenant demo_tenant --write
  PYTHONPATH=. python tools/semantic_catalog_tool.py validate --tenant demo_tenant

After DataHub ingest (repo root):
  ./scripts/refresh_datamart_metadata.sh
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Engine

from app.services.ai_services.datamart.config import WAREHOUSE_SCHEMA
from app.services.ai_services.datamart.workspace.runtime_context import (
    DatamartProfile,
    run_with_datamart_context,
)
from app.services.ai_services.datamart.schema import _get_engine
from app.services.ai_services.datamart.semantic.semantic_catalog_paths import (
    LEGACY_CATALOG_PATH,
    catalog_path_for_tenant_cli,
)
from app.services.ai_services.datamart.semantic.semantic_layer import clear_catalog_cache

CATALOG_PATH = LEGACY_CATALOG_PATH

CATALOG_HEADER = """\
# MintHRM semantic catalog — business vocabulary for the Datamart agent.
# Auto-maintained: run `python tools/semantic_catalog_tool.py refresh --write` after schema changes.
# Physical columns must still appear in the grounded allowlist (Postgres introspection).

"""

TENANT_CATALOG_HEADER = """\
# Per-tenant semantic catalog (ETL warehouse: hr_semantic, hr, hr_snap).
# Generated: python tools/semantic_catalog_tool.py refresh --tenant {tenant_id} --write

"""

# Fallback when catalog topic keywords do not match (legacy substring rules).
_TABLE_TOPIC_FALLBACK_RULES: list[tuple[str, str]] = [
    ("recruitment", "recruitment"),
    ("candidate", "recruitment"),
    ("performance", "performance_learning_development"),
    ("review", "performance_learning_development"),
    ("attrition", "employee_lifecycle"),
    ("snapshot", "past_data"),
    ("leave", "leave"),
    ("payroll", "payroll"),
    ("attendance", "attendance"),
    ("loan", "loan"),
    ("benefit", "benefit"),
    ("employee", "employee_information"),
]

_STUB_COLUMN_SUFFIXES = ("_id", "_name", "_date", "_days", "_amount", "_salary")


@dataclass
class WarehouseSnapshot:
    schema: str
    tables: list[str]
    columns_by_table: dict[str, set[str]]
    foreign_keys: list[dict[str, str]]
    column_comments: dict[str, dict[str, str]] = field(default_factory=dict)
    table_schemas: dict[str, str] = field(default_factory=dict)
    tenant_id: Optional[str] = None
    profile: str = "legacy_audit"


@dataclass
class RefreshReport:
    removed_dimensions: list[str] = field(default_factory=list)
    removed_joins: int = 0
    topics_tables_added: dict[str, list[str]] = field(default_factory=dict)
    topics_tables_removed: dict[str, list[str]] = field(default_factory=dict)
    joins_added: list[str] = field(default_factory=list)
    dimension_stubs_added: list[str] = field(default_factory=list)
    warehouse_only_tables: list[str] = field(default_factory=list)
    missing_tables: list[str] = field(default_factory=list)
    unknown_columns: dict[str, list[str]] = field(default_factory=dict)


def _load_catalog(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _save_catalog(path: Path, catalog: dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    text = yaml.dump(
        catalog,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    if tenant_id:
        header = TENANT_CATALOG_HEADER.format(tenant_id=tenant_id)
        meta = catalog.setdefault("catalog_meta", {})
        if isinstance(meta, dict):
            meta["tenant_id"] = tenant_id
    else:
        header = CATALOG_HEADER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + text, encoding="utf-8")
    clear_catalog_cache()


def _load_catalog_for_command(path: Path, tenant_id: Optional[str]) -> dict[str, Any]:
    if path.is_file():
        return _load_catalog(path)
    if tenant_id and LEGACY_CATALOG_PATH.is_file():
        catalog = copy.deepcopy(_load_catalog(LEGACY_CATALOG_PATH))
        meta = catalog.setdefault("catalog_meta", {})
        if isinstance(meta, dict):
            meta["tenant_id"] = tenant_id
            meta["derived_from"] = f"live_warehouse:{tenant_id}"
        return catalog
    return {}


def _infer_topic_for_table(table: str, catalog: dict[str, Any] | None = None) -> str:
    """Pick HRIS topic from catalog keywords, then fallback rules."""
    lower = table.lower()
    tokens = set(_table_keywords(table))
    topics: dict[str, Any] = (catalog or {}).get("topics") or {}
    best_topic: str | None = None
    best_score = 0
    for name, spec in topics.items():
        if not isinstance(spec, dict) or name.startswith("_"):
            continue
        score = 0
        for kw in spec.get("keywords") or []:
            if not isinstance(kw, str):
                continue
            kwl = kw.lower().strip().replace("_", " ")
            kw_us = kwl.replace(" ", "_")
            if kw_us in lower or kwl in lower:
                score += 4
            for tok in tokens:
                if tok in kwl or tok in kw_us or kw_us in tok:
                    score += 1
        if score > best_score:
            best_score = score
            best_topic = name
    if best_topic and best_score > 0:
        return best_topic
    if lower.startswith("vw_"):
        return "semantic_views"
    if lower.startswith("snap_"):
        return "past_data"
    for needle, topic in _TABLE_TOPIC_FALLBACK_RULES:
        if needle in lower:
            return topic
    if lower.startswith("dim_"):
        return "employee_information"
    if lower.startswith("fact_"):
        return "employee_information"
    if lower.startswith("mart_"):
        return "employee_information"
    return "warehouse_discovered"


def _table_keywords(table: str) -> list[str]:
    parts = re.findall(r"[a-z0-9]+", table.lower())
    return [p for p in parts if p not in ("dim", "fact", "vw", "view") and len(p) > 2]


def _schema_introspection_order(schemas: tuple[str, ...]) -> list[str]:
    preferred = ("hr", "hr_semantic", "hr_snap")
    ordered = [s for s in preferred if s in schemas]
    for s in schemas:
        if s not in ordered:
            ordered.append(s)
    return ordered


def snapshot_multi_schema(
    engine: Engine,
    schemas: tuple[str, ...],
    *,
    primary_schema: str,
    tenant_id: Optional[str] = None,
    profile: str = "tenant_etl",
) -> WarehouseSnapshot:
    """Merge tables/views across ETL schemas (short names; hr wins over semantic duplicates)."""
    inspector = sa_inspect(engine)
    tables: list[str] = []
    columns_by_table: dict[str, set[str]] = {}
    table_schemas: dict[str, str] = {}
    seen: set[str] = set()

    for schema in _schema_introspection_order(schemas):
        names: list[str] = []
        try:
            names.extend(inspector.get_table_names(schema=schema))
        except Exception:  # noqa: BLE001
            pass
        try:
            names.extend(inspector.get_view_names(schema=schema))
        except Exception:  # noqa: BLE001
            pass
        for table in names:
            key = table.lower()
            if key in seen:
                continue
            seen.add(key)
            tables.append(table)
            table_schemas[table] = schema
            try:
                cols = inspector.get_columns(table, schema=schema)
                columns_by_table[table] = {
                    str(c["name"]).lower() for c in cols if c.get("name")
                }
            except Exception:  # noqa: BLE001
                columns_by_table[table] = set()

    foreign_keys: list[dict[str, str]] = []
    fk_schema = "hr" if "hr" in schemas else primary_schema
    for table in tables:
        if table_schemas.get(table) != fk_schema:
            continue
        try:
            for fk in inspector.get_foreign_keys(table, schema=fk_schema) or []:
                constrained = fk.get("constrained_columns") or []
                referred_table = fk.get("referred_table") or ""
                referred_cols = fk.get("referred_columns") or []
                if not constrained or not referred_table or not referred_cols:
                    continue
                foreign_keys.append(
                    {
                        "left_table": table,
                        "left_column": constrained[0],
                        "right_table": referred_table,
                        "right_column": referred_cols[0],
                    }
                )
        except Exception:  # noqa: BLE001
            continue

    comments: dict[str, dict[str, str]] = {}
    for schema in _schema_introspection_order(schemas):
        schema_tables = [t for t in tables if table_schemas.get(t) == schema]
        comments.update(_fetch_column_comments(engine, schema_tables, schema=schema))

    return WarehouseSnapshot(
        schema=",".join(_schema_introspection_order(schemas)),
        tables=sorted(tables),
        columns_by_table=columns_by_table,
        foreign_keys=foreign_keys,
        column_comments=comments,
        table_schemas=table_schemas,
        tenant_id=tenant_id,
        profile=profile,
    )


def _snapshot_legacy() -> WarehouseSnapshot:
    engine = _get_engine()
    inspector = sa_inspect(engine)
    schema = WAREHOUSE_SCHEMA
    tables = sorted(inspector.get_table_names(schema=schema))
    columns_by_table: dict[str, set[str]] = {}
    foreign_keys: list[dict[str, str]] = []

    for table in tables:
        cols = inspector.get_columns(table, schema=schema)
        columns_by_table[table] = {str(c["name"]).lower() for c in cols if c.get("name")}
        for fk in inspector.get_foreign_keys(table, schema=schema) or []:
            constrained = fk.get("constrained_columns") or []
            referred_table = fk.get("referred_table") or ""
            referred_cols = fk.get("referred_columns") or []
            if not constrained or not referred_table or not referred_cols:
                continue
            foreign_keys.append(
                {
                    "left_table": table,
                    "left_column": constrained[0],
                    "right_table": referred_table,
                    "right_column": referred_cols[0],
                }
            )

    comments = _fetch_column_comments(engine, tables, schema=schema)
    return WarehouseSnapshot(
        schema=schema,
        tables=tables,
        columns_by_table=columns_by_table,
        foreign_keys=foreign_keys,
        column_comments=comments,
        table_schemas={t: schema for t in tables},
        profile="legacy_audit",
    )


def _snapshot_for_tenant(tenant_id: str) -> WarehouseSnapshot:
    from app.services.ai_services.datamart.workspace.runtime_context import require_datamart_context

    ctx = require_datamart_context()
    if ctx.profile == DatamartProfile.TENANT_ETL:
        return snapshot_multi_schema(
            ctx.engine,
            ctx.query_schemas,
            primary_schema=ctx.primary_schema,
            tenant_id=tenant_id,
            profile=ctx.profile.value,
        )
    return _snapshot_legacy()


def _snapshot_warehouse(tenant_id: Optional[str] = None) -> WarehouseSnapshot:
    if tenant_id:
        return run_with_datamart_context(tenant_id, _snapshot_for_tenant, tenant_id)
    return _snapshot_legacy()


def _fetch_column_comments(
    engine,
    tables: list[str],
    *,
    schema: str,
) -> dict[str, dict[str, str]]:
    """Postgres COMMENT ON COLUMN via pg_description."""
    from sqlalchemy import text

    if not tables:
        return {}
    sql = text(
        """
        SELECT c.table_name, c.column_name, pgd.description
        FROM information_schema.columns c
        JOIN pg_catalog.pg_statio_all_tables st
          ON st.schemaname = c.table_schema AND st.relname = c.table_name
        JOIN pg_catalog.pg_description pgd
          ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
        WHERE c.table_schema = :schema
          AND c.table_name = ANY(:tables)
          AND pgd.description IS NOT NULL
          AND trim(pgd.description) <> ''
        """
    )
    out: dict[str, dict[str, str]] = {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"schema": schema, "tables": tables}).fetchall()
        for table_name, col_name, desc in rows:
            out.setdefault(table_name, {})[col_name] = str(desc).strip()
    except Exception:  # noqa: BLE001
        return {}
    return out


def _catalog_table_column_refs(catalog: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for topic in (catalog.get("topics") or {}).values():
        if not isinstance(topic, dict):
            continue
        for table in topic.get("tables") or []:
            if isinstance(table, str):
                out.setdefault(table.lower(), set())
    for spec in (catalog.get("dimensions") or {}).values():
        if not isinstance(spec, dict):
            continue
        table = (spec.get("table") or "").strip()
        col = (spec.get("column") or "").strip()
        if table and col:
            out.setdefault(table.lower(), set()).add(col.lower())
    for spec in (catalog.get("metrics") or {}).values():
        if not isinstance(spec, dict):
            continue
        for table in spec.get("tables") or []:
            if isinstance(table, str):
                out.setdefault(table.lower(), set())
    return out


def validate_catalog(catalog: dict[str, Any], snap: WarehouseSnapshot) -> dict[str, Any]:
    warehouse_tables = {t.lower() for t in snap.tables}
    refs = _catalog_table_column_refs(catalog)
    report: dict[str, Any] = {
        "schema": snap.schema,
        "missing_tables": [],
        "unknown_columns": {},
        "warehouse_only": [],
    }
    for table, cols in sorted(refs.items()):
        if table not in warehouse_tables:
            report["missing_tables"].append(table)
            continue
        actual = next((t for t in snap.tables if t.lower() == table), table)
        live = snap.columns_by_table.get(actual, set())
        bad = sorted(c for c in cols if c not in live)
        if bad:
            report["unknown_columns"][table] = bad
    catalog_tables = set(refs)
    report["warehouse_only"] = sorted(
        t for t in snap.tables if t.lower() not in catalog_tables
    )
    return report


def _join_signature(j: dict[str, Any]) -> str:
    return "|".join(
        [
            str(j.get("left_table", "")).lower(),
            str(j.get("left_column", "")).lower(),
            str(j.get("right_table", "")).lower(),
            str(j.get("right_column", "")).lower(),
        ]
    )


def refresh_catalog(
    catalog: dict[str, Any],
    snap: WarehouseSnapshot,
    *,
    add_dimension_stubs: bool = False,
) -> RefreshReport:
    report = RefreshReport()
    warehouse_lower = {t.lower(): t for t in snap.tables}
    topics: dict[str, Any] = dict(catalog.get("topics") or {})
    dimensions: dict[str, Any] = dict(catalog.get("dimensions") or {})
    metrics: dict[str, Any] = dict(catalog.get("metrics") or {})
    joins: list[Any] = list(catalog.get("joins") or [])

    # --- Prune stale dimensions ---
    for key, spec in list(dimensions.items()):
        if not isinstance(spec, dict):
            continue
        table = (spec.get("table") or "").strip()
        column = (spec.get("column") or "").strip()
        actual = warehouse_lower.get(table.lower())
        if not actual:
            del dimensions[key]
            report.removed_dimensions.append(key)
            continue
        live_cols = snap.columns_by_table.get(actual, set())
        if column.lower() not in live_cols:
            del dimensions[key]
            report.removed_dimensions.append(key)

    # --- Prune stale metrics table refs ---
    for _name, spec in metrics.items():
        if not isinstance(spec, dict):
            continue
        tables = spec.get("tables") or []
        if isinstance(tables, list):
            spec["tables"] = [warehouse_lower.get(t.lower(), t) for t in tables if t.lower() in warehouse_lower]

    # --- Sync topic table lists ---
    all_topic_tables: set[str] = set()
    for topic_name, spec in list(topics.items()):
        if not isinstance(spec, dict):
            continue
        raw_tables = spec.get("tables") or []
        kept: list[str] = []
        removed: list[str] = []
        for t in raw_tables:
            if not isinstance(t, str):
                continue
            actual = warehouse_lower.get(t.lower())
            if actual:
                kept.append(actual)
                all_topic_tables.add(actual.lower())
            else:
                removed.append(t)
        if removed:
            report.topics_tables_removed[topic_name] = removed
        spec["tables"] = kept

    for table in snap.tables:
        if table.lower() in all_topic_tables:
            continue
        topic_key = _infer_topic_for_table(table, catalog)
        spec = topics.setdefault(topic_key, {"keywords": [], "tables": []})
        if not isinstance(spec, dict):
            spec = {"keywords": [], "tables": []}
            topics[topic_key] = spec
        if topic_key == "semantic_views" and not spec.get("keywords"):
            spec["keywords"] = ["semantic", "kpi", "summary", "view", "dashboard", "vw"]
        tables_list = spec.setdefault("tables", [])
        if not isinstance(tables_list, list):
            tables_list = []
            spec["tables"] = tables_list
        if table not in tables_list:
            tables_list.append(table)
            report.topics_tables_added.setdefault(topic_key, []).append(table)
        kw = spec.setdefault("keywords", [])
        if isinstance(kw, list):
            for token in _table_keywords(table):
                if token not in kw:
                    kw.append(token)
        all_topic_tables.add(table.lower())

    # --- Prune / enrich joins from FKs ---
    valid_joins: list[dict[str, Any]] = []
    existing_sigs = set()
    for j in joins:
        if not isinstance(j, dict):
            continue
        lt = str(j.get("left_table") or "")
        rt = str(j.get("right_table") or "")
        lc = str(j.get("left_column") or "")
        rc = str(j.get("right_column") or "")
        if lt.lower() not in warehouse_lower or rt.lower() not in warehouse_lower:
            report.removed_joins += 1
            continue
        left_actual = warehouse_lower[lt.lower()]
        right_actual = warehouse_lower[rt.lower()]
        if lc.lower() not in snap.columns_by_table.get(left_actual, set()):
            report.removed_joins += 1
            continue
        if rc.lower() not in snap.columns_by_table.get(right_actual, set()):
            report.removed_joins += 1
            continue
        j = {**j, "left_table": left_actual, "right_table": right_actual}
        valid_joins.append(j)
        existing_sigs.add(_join_signature(j))

    for fk in snap.foreign_keys:
        entry = {
            "left_table": fk["left_table"],
            "left_column": fk["left_column"],
            "right_table": fk["right_table"],
            "right_column": fk["right_column"],
            "purpose": (
                f"FK: {fk['left_table']}.{fk['left_column']} references "
                f"{fk['right_table']}.{fk['right_column']}."
            ),
        }
        sig = _join_signature(entry)
        if sig in existing_sigs:
            continue
        valid_joins.append(entry)
        existing_sigs.add(sig)
        report.joins_added.append(sig)

    # --- Optional dimension stubs for undocumented columns ---
    if add_dimension_stubs:
        for table, cols in snap.columns_by_table.items():
            for col in cols:
                if not any(col.endswith(s) for s in _STUB_COLUMN_SUFFIXES):
                    continue
                key = col
                if key in dimensions:
                    continue
                if any(
                    isinstance(spec, dict)
                    and (spec.get("table") or "").lower() == table.lower()
                    and (spec.get("column") or "").lower() == col
                    for spec in dimensions.values()
                ):
                    continue
                synonyms = [col.replace("_", " ")]
                comment = ""
                for cname, ctext in snap.column_comments.get(table, {}).items():
                    if cname.lower() == col:
                        comment = ctext
                        break
                if comment:
                    synonyms.append(comment[:80])
                dimensions[key] = {
                    "table": table,
                    "column": col,
                    "synonyms": synonyms[:4],
                }
                report.dimension_stubs_added.append(f"{table}.{col}")

    val = validate_catalog(
        {"topics": topics, "dimensions": dimensions, "metrics": metrics, "joins": valid_joins},
        snap,
    )
    report.missing_tables = val["missing_tables"]
    report.unknown_columns = val["unknown_columns"]
    report.warehouse_only_tables = val["warehouse_only"]

    catalog["topics"] = topics
    catalog["dimensions"] = dimensions
    catalog["metrics"] = metrics
    catalog["joins"] = valid_joins
    return report


def _print_refresh_report(report: RefreshReport, *, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"=== semantic catalog refresh ({mode}) ===")
    if report.removed_dimensions:
        print(f"Removed stale dimensions: {', '.join(report.removed_dimensions)}")
    if report.removed_joins:
        print(f"Removed stale joins: {report.removed_joins}")
    for topic, added in report.topics_tables_added.items():
        print(f"Topic '{topic}' +tables: {', '.join(added)}")
    for topic, removed in report.topics_tables_removed.items():
        print(f"Topic '{topic}' -tables: {', '.join(removed)}")
    if report.joins_added:
        print(f"Added joins from FK metadata: {len(report.joins_added)}")
    if report.dimension_stubs_added:
        print(f"Added dimension stubs: {', '.join(report.dimension_stubs_added)}")
    if report.warehouse_only_tables:
        print(f"Tables still not in any topic ref: {', '.join(report.warehouse_only_tables[:20])}")
    if report.missing_tables or report.unknown_columns:
        print("WARNING: validation issues remain after refresh:")
        print(json.dumps(
            {
                "missing_tables": report.missing_tables,
                "unknown_columns": report.unknown_columns,
            },
            indent=2,
        ))


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain semantic_catalog.yaml")
    parser.add_argument(
        "command",
        choices=("validate", "refresh", "report"),
        help="validate | refresh | report",
    )
    parser.add_argument(
        "--tenant",
        metavar="TENANT_ID",
        help="ETL tenant id (writes semantic_catalogs/{tenant}.yaml, multi-schema snapshot)",
    )
    parser.add_argument("--catalog", type=Path, default=None, help="Catalog YAML path")
    parser.add_argument("--json", metavar="PATH", help="Write JSON output (report/validate)")
    parser.add_argument(
        "--write",
        action="store_true",
        help="refresh: write catalog to disk (default is dry-run)",
    )
    parser.add_argument(
        "--add-dimension-stubs",
        action="store_true",
        help="refresh: add stub dimensions for new *_id/*_name columns",
    )
    args = parser.parse_args()
    tenant_id = (args.tenant or "").strip() or None
    catalog_path = args.catalog
    if catalog_path is None:
        catalog_path = (
            catalog_path_for_tenant_cli(tenant_id)
            if tenant_id
            else CATALOG_PATH
        )

    try:
        snap = _snapshot_warehouse(tenant_id)
    except Exception as exc:  # noqa: BLE001
        print(f"Warehouse unreachable: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if not snap.tables:
        print(f"No tables in schema(s) {snap.schema}", file=sys.stderr)
        raise SystemExit(2)

    if tenant_id:
        print(
            f"Tenant {tenant_id} profile={snap.profile} "
            f"schemas={snap.schema} tables={len(snap.tables)}"
        )

    catalog = _load_catalog_for_command(catalog_path, tenant_id)

    if args.command == "validate":
        report = validate_catalog(catalog, snap)
        if args.json:
            Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Wrote {args.json}")
        else:
            print(json.dumps(report, indent=2))
        if report["missing_tables"] or report["unknown_columns"]:
            raise SystemExit(1)
        return

    if args.command == "report":
        report = validate_catalog(catalog, snap)
        payload = {
            "validation": report,
            "warehouse": {
                "schema": snap.schema,
                "table_count": len(snap.tables),
                "tables": snap.tables,
                "foreign_key_count": len(snap.foreign_keys),
            },
        }
        if args.json:
            Path(args.json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Wrote {args.json}")
        else:
            print(json.dumps(payload, indent=2))
        return

    if args.command == "refresh":
        dry_run = not args.write
        refresh_report = refresh_catalog(
            catalog,
            snap,
            add_dimension_stubs=args.add_dimension_stubs,
        )
        _print_refresh_report(refresh_report, dry_run=dry_run)
        if args.write:
            _save_catalog(catalog_path, catalog, tenant_id=tenant_id)
            print(f"Wrote {catalog_path}")
        else:
            print("\nNo files changed. Re-run with --write to apply.")
        if refresh_report.missing_tables or refresh_report.unknown_columns:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
