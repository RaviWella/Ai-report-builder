"""Load and validate HR datamart ER metadata against dbt models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
META_PATH = REPO_ROOT / "docs" / "datamart-er.yml"


@dataclass(frozen=True)
class EntityRow:
    name: str
    kind: str
    pk: str
    grain: str


@dataclass(frozen=True)
class RelRow:
    from_model: str
    to_model: str
    label: str


def _infer_kind(name: str) -> str:
    if name.startswith("dim_"):
        return "DIM"
    if name.startswith("fct_") or name.startswith("fact_"):
        return "FACT"
    if name.startswith("mart_"):
        return "MART"
    if name.startswith("vw_"):
        return "VIEW"
    return "OTHER"


def _infer_pk(name: str, kind: str) -> str:
    if kind in ("MART", "VIEW"):
        return "-"
    if name.startswith("dim_"):
        suffix = name[4:]
        return f"{suffix}_sk"
    if name.startswith("fct_"):
        body = name[4:]
        return f"{body}_sk" if not body.endswith("_sk") else body
    if name.startswith("fact_"):
        return "id"
    return "-"


def load_meta() -> dict[str, Any]:
    with META_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_entities(domain: str, meta: dict[str, Any]) -> list[EntityRow]:
    names: list[str] = sorted(meta["domain_models"][domain])
    overrides: dict[str, Any] = meta.get("model_meta") or {}
    rows: list[EntityRow] = []
    for name in names:
        o = overrides.get(name) or {}
        kind = str(o.get("kind") or _infer_kind(name))
        pk = str(o.get("pk") or _infer_pk(name, kind))
        grain = str(o.get("grain") or "")
        rows.append(EntityRow(name=name, kind=kind, pk=pk, grain=grain))
    return rows


def build_relationships(domain: str, meta: dict[str, Any]) -> list[RelRow]:
    rels = meta["relationships"][domain]
    return [
        RelRow(
            from_model=str(r["from"]),
            to_model=str(r["to"]),
            label=str(r["label"]),
        )
        for r in rels
    ]


def build_semantic_views(meta: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    meta = meta or load_meta()
    return [(str(v["name"]), str(v["reads"])) for v in meta["semantic_views"]]


def entity_tuples(domain: str, meta: dict[str, Any] | None = None) -> list[tuple[str, str, str, str]]:
    meta = meta or load_meta()
    return [(e.name, e.kind, e.pk, e.grain) for e in build_entities(domain, meta)]


def rel_tuples(domain: str, meta: dict[str, Any] | None = None) -> list[tuple[str, str, str]]:
    meta = meta or load_meta()
    return [(r.from_model, r.to_model, r.label) for r in build_relationships(domain, meta)]


def _planned_model_names(meta: dict[str, Any], domain: str) -> list[str]:
    block = (meta.get("planned_domain_models") or {}).get(domain) or {}
    names: list[str] = []
    for key in ("shared_dimensions", "new_dimensions", "facts", "marts", "semantic_views"):
        names.extend(block.get(key) or [])
    return sorted(set(names))


def build_planned_entities(domain: str, meta: dict[str, Any] | None = None) -> list[EntityRow]:
    meta = meta or load_meta()
    overrides: dict[str, Any] = meta.get("planned_model_meta") or {}
    rows: list[EntityRow] = []
    for name in _planned_model_names(meta, domain):
        o = overrides.get(name) or {}
        kind = str(o.get("kind") or _infer_kind(name))
        pk = str(o.get("pk") or _infer_pk(name, kind))
        grain = str(o.get("grain") or "planned")
        rows.append(EntityRow(name=name, kind=kind, pk=pk, grain=grain))
    return rows


def planned_entity_tuples(domain: str, meta: dict[str, Any] | None = None) -> list[tuple[str, str, str, str]]:
    return [(e.name, e.kind, e.pk, e.grain) for e in build_planned_entities(domain, meta)]


def build_planned_relationships(domain: str, meta: dict[str, Any] | None = None) -> list[RelRow]:
    meta = meta or load_meta()
    rels = (meta.get("planned_relationships") or {}).get(domain) or []
    return [
        RelRow(
            from_model=str(r["from"]),
            to_model=str(r["to"]),
            label=str(r["label"]),
        )
        for r in rels
    ]


def planned_rel_tuples(domain: str, meta: dict[str, Any] | None = None) -> list[tuple[str, str, str]]:
    meta = meta or load_meta()
    return [(r.from_model, r.to_model, r.label) for r in build_planned_relationships(domain, meta)]


def _sql_stems(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {p.stem for p in path.glob("*.sql")}


def discover_dbt_marts(meta: dict[str, Any]) -> dict[str, set[str]]:
    disc = meta["dbt_discovery"]
    employment = _sql_stems(REPO_ROOT / disc["employment_marts"])
    payroll = _sql_stems(REPO_ROOT / disc["payroll_marts"])
    leave = _sql_stems(REPO_ROOT / disc["leave_marts"])
    legacy_dir = REPO_ROOT / disc["legacy_marts"]
    legacy = _sql_stems(legacy_dir)
    # Root-level marts only (not subfolders)
    legacy_root = {p.stem for p in legacy_dir.glob("*.sql")}
    semantic = _sql_stems(REPO_ROOT / disc["semantic_views"])
    return {
        "employment": employment,
        "payroll": payroll,
        "leave": leave,
        "legacy_root": legacy_root,
        "semantic": semantic,
        "all_marts_union": employment | payroll | leave | legacy,
    }


def all_domain_models(meta: dict[str, Any] | None = None) -> set[str]:
    meta = meta or load_meta()
    names: set[str] = set()
    for domain in meta.get("domains") or meta.get("domain_models") or {}:
        names.update(meta["domain_models"].get(domain) or [])
    return names


def build_control_plane(meta: dict[str, Any] | None = None) -> list[tuple[str, str, str, str]]:
    """Return (name, kind, pk, grain) rows for hr_control governance tables."""
    meta = meta or load_meta()
    block = meta.get("control_plane") or {}
    rows: list[tuple[str, str, str, str]] = []
    for obj in block.get("objects") or []:
        rows.append(
            (
                str(obj.get("name", "")),
                str(obj.get("kind", "TABLE")),
                str(obj.get("pk", "-")),
                str(obj.get("grain", "")),
            )
        )
    return rows


def build_control_plane_semantic(meta: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    meta = meta or load_meta()
    block = meta.get("control_plane") or {}
    return [
        (str(v.get("name", "")), str(v.get("reads", "")))
        for v in block.get("semantic_exposure") or []
    ]


def validate(meta: dict[str, Any] | None = None) -> list[str]:
    """Return human-readable errors; empty list means OK."""
    meta = meta or load_meta()
    errors: list[str] = []
    discovered = discover_dbt_marts(meta)
    all_models = all_domain_models(meta)

    domain_disk_expectations: dict[str, set[str]] = {
        "enterprise": discovered["employment"] | {"dim_employee"},
        "leave": discovered["leave"] | {"fact_leave_balance", "dim_employee", "dim_date"},
        "payroll": discovered["payroll"] | {"dim_employee", "fact_payroll"},
    }

    for domain in ("enterprise", "leave", "payroll"):
        documented = set(meta["domain_models"][domain])
        expected_on_disk = domain_disk_expectations[domain]

        missing_from_yaml = sorted(expected_on_disk - documented)
        extra_in_yaml = sorted(documented - expected_on_disk)
        if missing_from_yaml:
            errors.append(
                f"[{domain}] Add to docs/datamart-er.yml domain_models: {', '.join(missing_from_yaml)}"
            )
        if extra_in_yaml:
            errors.append(
                f"[{domain}] Remove from domain_models or add dbt model: {', '.join(extra_in_yaml)}"
            )

        entities = {e.name for e in build_entities(domain, meta)}
        for r in build_relationships(domain, meta):
            if r.from_model not in entities:
                errors.append(f"[{domain}] relationship from unknown model: {r.from_model}")
            if r.to_model not in all_models:
                errors.append(f"[{domain}] relationship to unknown model: {r.to_model}")

    documented_semantic = {v[0] for v in build_semantic_views(meta)}
    on_disk_semantic = discovered["semantic"]
    if missing := sorted(on_disk_semantic - documented_semantic):
        errors.append(f"[semantic] Add semantic_views entries: {', '.join(missing)}")
    if extra := sorted(documented_semantic - on_disk_semantic):
        errors.append(f"[semantic] Remove or add dbt view: {', '.join(extra)}")

    legacy = discovered["legacy_root"]
    unassigned = legacy - discovered["employment"] - discovered["payroll"]
  # dim_employee, fact_* at root should be assigned in yaml
    for name in sorted(unassigned):
        if name in ("dim_employee", "fact_leave_balance", "fact_payroll", "fact_attendance"):
            continue
        errors.append(
            f"[dbt] Legacy mart '{name}' at models/marts/ — assign to enterprise or payroll in datamart-er.yml"
        )

    return errors
