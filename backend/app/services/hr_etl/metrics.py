"""HR Metric Resolver — reads hr_metrics.yaml and computes values
from the semantic layer.

Mirrors finance_etl/metrics.py pattern exactly.

Two kinds of metrics:
  1. dimension_filter metrics — direct aggregation over fact tables
  2. formula metrics — computed from other metrics via `formula:` field

All metric values come from the AI-safe semantic layer:
  {tenant_id}_hr_semantic.vw_*
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("hr_etl.metrics")

METRICS_YAML = Path(__file__).parents[2] / "rules" / "hr_semantic" / "hr_metrics.yaml"


class UnsupportedFilterError(ValueError):
    """Raised when a caller passes a filter the metric's fetch path cannot apply."""


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class HrMetricDef:
    name: str
    display_name: str
    description: str
    unit: str                   # count | percent | currency | days | hours
    category: str               # headcount | turnover | payroll | attendance | leave | performance
    aggregation: Optional[str] = None
    dimension_filter: Optional[dict] = None
    period_column: Optional[str] = None
    formula: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    semantic_view: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    rankable: Optional[bool] = None
    good_direction: Optional[str] = None   # up | down
    note: Optional[str] = None

    @property
    def is_rankable(self) -> bool:
        if self.rankable is not None:
            return bool(self.rankable)
        if self.formula:
            return False
        if self.aggregation in ("rate", "ratio", "percent"):
            return False
        return bool(self.dimension_filter)


@dataclass
class HrMetricValue:
    name: str
    display_name: str
    unit: str
    value: Optional[float]
    period_label: Optional[str] = None
    department_id: Optional[int] = None
    branch_id: Optional[int] = None
    derivation: str = ""
    components: dict[str, float] = field(default_factory=dict)


# ── Registry ─────────────────────────────────────────────────────────

class HrMetricRegistry:
    def __init__(self, path: Path = METRICS_YAML):
        self.path = path
        self._cache: dict[str, HrMetricDef] = {}
        self._aliases: dict[str, str] = {}
        self._mtime: float = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            logger.warning("hr_metrics.yaml not found at %s", self.path)
            return
        doc = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self._cache = {}
        self._aliases = {}
        for m in doc.get("metrics", []):
            mdef = HrMetricDef(
                name=m["name"],
                display_name=m.get("display_name", m["name"]),
                description=m.get("description", "").strip(),
                unit=m.get("unit", "count"),
                category=m.get("category", "other"),
                aggregation=m.get("aggregation"),
                dimension_filter=m.get("dimension_filter"),
                period_column=m.get("period_column"),
                formula=m.get("formula"),
                depends_on=m.get("depends_on", []) or [],
                semantic_view=m.get("semantic_view"),
                aliases=m.get("aliases", []) or [],
                rankable=m.get("rankable"),
                good_direction=m.get("good_direction"),
                note=m.get("note"),
            )
            self._cache[mdef.name] = mdef
            for a in mdef.aliases:
                self._aliases[a.lower()] = mdef.name
        self._mtime = self.path.stat().st_mtime
        logger.info(
            "hr_metrics.yaml loaded: %d metrics, %d aliases",
            len(self._cache), len(self._aliases),
        )

    def _maybe_reload(self) -> None:
        if not self.path.exists():
            return
        if self.path.stat().st_mtime > self._mtime:
            self._load()

    def get(self, name: str) -> Optional[HrMetricDef]:
        self._maybe_reload()
        key = name.strip()
        if key in self._cache:
            return self._cache[key]
        resolved = self._aliases.get(key.lower())
        return self._cache.get(resolved) if resolved else None

    def all(self) -> list[HrMetricDef]:
        self._maybe_reload()
        return list(self._cache.values())


_registry: Optional[HrMetricRegistry] = None


def registry() -> HrMetricRegistry:
    global _registry
    if _registry is None:
        _registry = HrMetricRegistry()
    return _registry


# ── Resolver ─────────────────────────────────────────────────────────

class HrMetricResolver:
    """Compute an HrMetricDef's value against the semantic layer."""

    def __init__(self, pg: Engine, tenant_id: str):
        self.pg = pg
        self.tenant_id = tenant_id
        from app.services.hr_etl.schema_names import semantic_schema

        self.semantic = semantic_schema(tenant_id)

    def resolve(
        self,
        name: str,
        period_label: Optional[str] = None,
        department_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        filters: Optional[dict] = None,
    ) -> Optional[HrMetricValue]:
        mdef = registry().get(name)
        if not mdef:
            return None

        _filters = dict(filters or {})
        if department_id and "department_id" not in _filters:
            _filters["department_id"] = department_id
        if branch_id and "branch_id" not in _filters:
            _filters["branch_id"] = branch_id
        if period_label and "period_label" not in _filters:
            _filters["period_label"] = period_label

        if mdef.formula and mdef.depends_on:
            return self._resolve_formula(mdef, _filters)
        if mdef.dimension_filter:
            return self._resolve_dimension_filter(mdef, _filters)

        return HrMetricValue(
            name=mdef.name, display_name=mdef.display_name, unit=mdef.unit,
            value=None, derivation="no dimension_filter or formula defined",
        )

    def _resolve_dimension_filter(
        self, mdef: HrMetricDef, filters: dict
    ) -> HrMetricValue:
        view = mdef.semantic_view or self._default_view(mdef)
        filt = mdef.dimension_filter or {}
        agg_col = filt.get("agg_col", "1")
        agg_fn = filt.get("agg_fn", "COUNT")
        status_filter = filt.get("status")

        where: list[str] = []
        params: dict[str, Any] = {}

        status_col = filt.get("status_column", "status")
        if status_filter:
            where.append(f"{status_col} = :status_flt")
            params["status_flt"] = status_filter

        if filters.get("department_id"):
            where.append("department_id = :dept_id")
            params["dept_id"] = filters["department_id"]

        if filters.get("branch_id"):
            where.append("branch_id = :branch_id")
            params["branch_id"] = filters["branch_id"]

        period_col = filt.get("period_column") or mdef.period_column
        if filters.get("period_label") and period_col:
            where.append(f"{period_col} = :period_label")
            params["period_label"] = filters["period_label"]

        where_sql = "WHERE " + " AND ".join(where) if where else ""
        sql = (
            f'SELECT {agg_fn}({agg_col}) AS val'
            f' FROM "{self.semantic}".{view}'
            f" {where_sql}"
        )

        with self.pg.connect() as conn:
            val = conn.execute(text(sql), params).scalar()

        return HrMetricValue(
            name=mdef.name,
            display_name=mdef.display_name,
            unit=mdef.unit,
            value=float(val) if val is not None else 0.0,
            period_label=filters.get("period_label"),
            department_id=filters.get("department_id"),
            branch_id=filters.get("branch_id"),
            derivation=f"{agg_fn}({agg_col}) on {view}; filters={filters}",
        )

    def _default_view(self, mdef: HrMetricDef) -> str:
        mapping = {
            "headcount":   "vw_headcount",
            "turnover":    "vw_turnover",
            "payroll":     "vw_payroll_summary",
            "attendance":  "vw_attendance_summary",
            "leave":       "vw_leave_summary",
            "performance": "vw_performance_summary",
        }
        return mapping.get(mdef.category, "vw_headcount")

    def _resolve_formula(
        self, mdef: HrMetricDef, filters: dict
    ) -> HrMetricValue:
        components: dict[str, float] = {}
        for dep_name in mdef.depends_on:
            dep_val = self.resolve(dep_name, filters=filters)
            if dep_val is None or dep_val.value is None:
                return HrMetricValue(
                    name=mdef.name, display_name=mdef.display_name, unit=mdef.unit,
                    value=None, derivation=f"Missing component: {dep_name}",
                )
            components[dep_name] = dep_val.value

        try:
            value = _evaluate_formula(mdef.formula or "", components)
        except Exception as exc:
            return HrMetricValue(
                name=mdef.name, display_name=mdef.display_name, unit=mdef.unit,
                value=None, derivation=f"Formula error: {exc}",
                components=components,
            )

        return HrMetricValue(
            name=mdef.name, display_name=mdef.display_name, unit=mdef.unit,
            value=value,
            derivation=f"formula = {mdef.formula}",
            components=components,
        )


# ── Safe formula evaluator (identical to finance_etl) ────────────────

_SAFE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _evaluate_formula(expr: str, values: dict[str, float]) -> float:
    if not expr:
        return 0.0
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[+\-*/()]|\S", expr
    )
    for t in tokens:
        if _SAFE_NAME_RE.match(t) and not t.replace(".", "").isdigit():
            if t not in values:
                raise ValueError(f"Unknown name in formula: {t}")
        elif t in "+-*/()":
            continue
        else:
            try:
                float(t)
            except ValueError:
                raise ValueError(f"Unexpected token: {t!r}")
    return float(eval(expr, {"__builtins__": {}}, dict(values)))  # noqa: S307
