"""Semantic layer domain models (SRS §4.1, Architecture §4.3).

The semantic catalogue maps business concepts (e.g. "Employee Name") to physical
tables/columns per tenant, plus joins and measures. NOTHING outside this layer
knows physical names: the AI sees only `ref`/`label`/`type`; the Query Engine
resolves `ref` -> physical table/column through here.

A `ref` is a stable, business-facing key of the form "<entity>.<field>"
(e.g. "employee.full_name"). Physical names live ONLY in `PhysicalColumn`.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.domain.enums import AggFn, FieldRole, FieldType, FilterOp

_METRIC_REF = re.compile(r"metric\.[A-Za-z0-9_]+")


class MetricFilter(BaseModel):
    """A scope condition baked into a metric (e.g. status = active), applied as an
    aggregate FILTER so it composes with any grouping the report adds."""

    ref: str
    op: FilterOp
    value: object | None = None


class MetricDef(BaseModel):
    """A canonical, governed metric — the single definition for a business number,
    so 'Headcount' or 'Total Net Pay' means the same thing in every report (the
    mint-analytics rigor, adapted to our per-tenant catalogue).

    Referenced from a report as `metric.<key>`. Three kinds:
      - aggregate: `agg(ref)` over a measure (sum/avg/min/max), optional filters.
      - count:     `count(ref|*)` (optionally distinct), optional filters.
      - formula:   arithmetic over OTHER metrics (`metric.<k>` + - * / and numbers),
                   so ratios and nets compute from totals, e.g.
                   net = metric.total_gross - metric.total_deductions.
    """

    key: str  # stable; the ref is "metric.<key>"
    label: str
    description: str | None = None
    unit: str | None = None  # currency | count | percent | number
    kind: str  # "aggregate" | "count" | "formula"
    agg: AggFn | None = None
    ref: str | None = None  # measure ref (aggregate); count target or None for count(*)
    distinct: bool = False  # count distinct
    expression: str | None = None  # formula over metric.<k>
    filters: list[MetricFilter] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)  # NL phrases → this metric
    source: str = "custom"  # seed | introspected | custom
    # Governance (stored in the metric JSON — no migration). A certified metric is
    # the approved single definition of a business number; the AI/picker prefer it,
    # and re-defining one requires explicit re-certification (no silent drift).
    certified: bool = False
    certified_by: str | None = None
    certified_at: str | None = None  # ISO-8601, stamped when certified
    owner: str | None = None


class GlossaryTerm(BaseModel):
    """A governed business-term definition — the bridge between business language
    and the technical catalogue. A term (e.g. "Take-home Pay") carries its
    plain-language meaning AND points at the governed `ref` that computes it
    (a `metric.<key>` or a field `<entity>.<field>`).

    Two jobs:
      - grounds the deterministic NL resolver: a term's synonyms resolve to its
        `ref`, so "in-hand salary by branch" hits `metric.total_net` exactly.
      - documents the layer for humans: the builder UI shows the definition, so a
        word means the same thing for every user of the tenant.

    `ref` is optional — a term can be purely documentary (no computation yet).
    Per-tenant, so a client can add its own vocabulary.
    """

    term: str  # canonical business term, e.g. "Take-home Pay"
    aliases: list[str] = Field(default_factory=list)  # synonyms / NL phrases
    definition: str  # plain-language meaning (shown in UI, given to the AI)
    ref: str | None = None  # the governed metric.<key> or field ref it resolves to
    category: str | None = None  # payroll | workforce | leave | attendance | ...
    source: str = "custom"  # seed | custom

    def key(self) -> str:
        """Stable slug derived from the term (storage + supersede key)."""
        return re.sub(r"[^a-z0-9]+", "_", self.term.strip().lower()).strip("_")


class PhysicalColumn(BaseModel):
    """Where a semantic field physically lives. Never exposed to the AI."""

    table: str  # physical table/view, e.g. "mart_employee_current"
    column: str  # physical column, e.g. "full_name"
    schema_name: str | None = None  # defaults to entity.base_schema if None
    # Set when `column` is a JSON/JSONB column and this field is one KEY inside
    # it (e.g. a tenant's dynamic "extra fields" blob) rather than the column
    # itself — compiles to `column ->> 'json_key'`, the key bound as a
    # parameter (see query_engine/sql_builder.col_for), never string-built SQL.
    json_key: str | None = None


class SemanticField(BaseModel):
    """A single business concept (dimension or measure)."""

    ref: str  # "<entity>.<field>" — stable business key (the only thing the AI sees)
    label: str  # human label, e.g. "Employee Name"
    description: str | None = None
    type: FieldType
    role: FieldRole
    physical: PhysicalColumn
    # For measures: which aggregations are valid (FR-B3). Empty => raw value only.
    allowed_aggregations: list[AggFn] = Field(default_factory=list)
    # For enum-like dimensions, optional known values (helps the builder UI / AI).
    sample_values: list[str] | None = None
    # Business synonyms (from the governed data dictionary) — extra phrases the Excel/
    # NL column matcher scores against, so "in-hand salary" maps to net pay. Never a
    # physical name; safe for matching, kept out of the AI physical projection.
    synonyms: list[str] = Field(default_factory=list)
    pii: bool = False  # informational; PII never reaches the AI regardless


class JoinDef(BaseModel):
    """A predefined join between two entities (Architecture §4.3).

    The Query Engine only ever composes joins declared here — it never infers a
    join. left/right are entity names; the keys are physical column names on each
    entity's base table.
    """

    left_entity: str
    right_entity: str
    left_key: str  # physical column on left base table (e.g. "employee_sk")
    right_key: str  # physical column on right base table
    join_type: str = "inner"  # inner | left


class PeriodGrain(BaseModel):
    """Marks an entity as *period-grained* — one row per employee per payroll
    period — and names the physical (year, month) columns that identify the
    period. The Query Engine aligns joins between two period-grained marts on
    these columns so they don't cross-multiply rows across periods.

    Optional: when absent, the compiler infers the grain from exposed year/month
    fields, so catalogues pinned before this existed still align correctly.
    """

    year_column: str  # physical column, e.g. "payroll_year" | "year"
    month_column: str  # physical column, e.g. "payroll_month" | "month"


class Entity(BaseModel):
    """A reporting entity (Employee, Department, Leave, Attendance, Payroll …).

    `base_table` is the canonical physical object for the entity in `base_schema`
    (often an hr_semantic view, which insulates us from mart churn per the ER doc).
    """

    name: str  # "Employee"
    key: str  # "employee" — used as the ref prefix
    base_schema: str  # "hr_semantic" | "hr"
    base_table: str  # "vw_..." or "mart_..." / "dim_..."
    primary_key: str  # physical PK column, e.g. "employee_sk"
    description: str | None = None
    fields: list[SemanticField] = Field(default_factory=list)
    # Set for marts whose grain is employee × payroll period (payroll, paysheet,
    # attendance, …). Drives period-aligned joins. None => inferred by the compiler.
    period_grain: PeriodGrain | None = None


class SemanticCatalog(BaseModel):
    """The full per-tenant catalogue stored as JSONB in `semantic_models.catalog`.

    `version` is the pin written onto every report version (`semantic_version_ref`)
    so old reports regenerate correctly after the mapping changes (SRS §7.3).
    """

    tenant_id: str
    version: int
    entities: list[Entity] = Field(default_factory=list)
    joins: list[JoinDef] = Field(default_factory=list)
    # Canonical metrics layer (governed named measures), keyed `metric.<key>`.
    metrics: list[MetricDef] = Field(default_factory=list)
    # Business glossary (governed term -> definition -> ref), per tenant.
    glossary: list[GlossaryTerm] = Field(default_factory=list)

    # ---- resolution helpers (used by the Query Engine) ----
    def field_index(self) -> dict[str, SemanticField]:
        return {f.ref: f for e in self.entities for f in e.fields}

    # Datamart business identity columns (DATAMART_MART_SPEC identity group).
    # Surrogate `employee_sk` is the join key, not the issuer-facing record id.
    _RECORD_IDENTITY_COLUMNS = frozenset({"employee_no", "emp_no"})

    def record_identity_ref(self) -> str | None:
        """Business ref of the unique record key on the anchor entity.

        Resolved from this catalogue's physical mapping — the designer stores
        whatever `ref` this tenant assigned, never a hardcoded HR name.
        """
        if not self.entities:
            return None
        for f in self.entities[0].fields:
            if f.physical.column in self._RECORD_IDENTITY_COLUMNS:
                return f.ref
        return None

    def metric_index(self) -> dict[str, MetricDef]:
        return {m.key: m for m in self.metrics}

    def glossary_index(self) -> dict[str, GlossaryTerm]:
        return {t.key(): t for t in self.glossary}

    def synonyms_for_ref(self) -> dict[str, list[str]]:
        """ref -> extra NL phrases the glossary contributes for it (term + aliases).
        Lets the deterministic resolver match business language onto the governed
        ref a term points at, without re-deriving anything. Only terms with a `ref`
        contribute; the ref must exist (validated on define, but resolved leniently
        here so a stale term never breaks resolution)."""
        out: dict[str, list[str]] = {}
        for t in self.glossary:
            if t.ref:
                out.setdefault(t.ref, []).extend([t.term, *t.aliases])
        return out

    def expand_field_refs(self, refs: object) -> set[str]:
        """Resolve a set of refs to the underlying FIELD refs on physical tables:
        `metric.<k>` expands to its measure + filter refs (recursively through
        formula metrics); `calc.<n>` is dropped (handled separately). Shared by the
        compiler and the guards so metric entities/joins are validated and built."""
        midx = self.metric_index()
        out: set[str] = set()

        def _under(key: str, seen: set[str]) -> None:
            if key in seen:
                return
            seen.add(key)
            m = midx.get(key)
            if m is None:
                return
            if m.ref:
                out.add(m.ref)
            out.update(f.ref for f in m.filters)
            if m.expression:
                for tok in _METRIC_REF.findall(m.expression):
                    _under(tok.split(".", 1)[1], seen)

        for r in refs:
            if r.startswith("metric."):
                _under(r.split(".", 1)[1], set())
            elif not r.startswith("calc."):
                out.add(r)
        return out

    def entity_by_key(self) -> dict[str, Entity]:
        return {e.key: e for e in self.entities}

    def root_for(self, entity_keys: set[str], preferred: str) -> str:
        """Pick a root entity from which ALL `entity_keys` are reachable via the
        declared joins (joins are bidirectional). Prefers `preferred` when it
        works; otherwise tries each referenced entity. Returns `preferred` if no
        single root reaches them all (validate_joins then raises a clear error).
        Generic — lets the root track the chosen fields, not a fixed default."""
        if not entity_keys:
            return preferred
        adj: dict[str, set[str]] = {e.key: set() for e in self.entities}
        name_to_key = {e.name: e.key for e in self.entities}
        for j in self.joins:
            a = name_to_key.get(j.left_entity, j.left_entity)
            b = name_to_key.get(j.right_entity, j.right_entity)
            if a in adj and b in adj:
                adj[a].add(b)
                adj[b].add(a)

        def reach(start: str) -> set[str]:
            seen, stack = {start}, [start]
            while stack:
                for m in adj.get(stack.pop(), ()):
                    if m not in seen:
                        seen.add(m)
                        stack.append(m)
            return seen

        for cand in [preferred, *sorted(entity_keys)]:
            if cand in adj and entity_keys <= reach(cand):
                return cand
        return preferred

    def resolve(self, ref: str) -> SemanticField:
        """Raises ValueError (not KeyError) for an unknown ref — every API route
        that runs a report already catches ValueError and turns it into a clean
        400; a bare KeyError would instead escape as an opaque 500 (a stale
        field ref after a semantic-layer rebuild is a normal, user-facing
        situation, not an internal error)."""
        idx = self.field_index()
        if ref not in idx:
            raise ValueError(f"Unknown semantic ref: {ref!r}")
        return idx[ref]

    def entity_of_ref(self, ref: str) -> Entity:
        """See resolve() — ValueError, not KeyError, for the same reason."""
        entity_key = ref.split(".", 1)[0]
        ents = self.entity_by_key()
        if entity_key not in ents:
            raise ValueError(f"Unknown entity for ref: {ref!r}")
        return ents[entity_key]

    def metadata_for_ai(self) -> list[dict]:
        """Metadata-only projection handed to the AI Adapter (NO physical names,
        NO data). This is the ONLY shape of catalogue the AI ever sees. Canonical
        metrics are appended as pre-aggregated `metric.<key>` measures, so the AI
        (and the field picker) reference governed numbers rather than re-deriving."""
        fields = [
            {
                "ref": f.ref,
                "label": f.label,
                "type": f.type.value,
                "role": f.role.value,
                "entity": e.name,
                "description": f.description,
                "allowed_aggregations": [a.value for a in f.allowed_aggregations],
            }
            for e in self.entities
            for f in e.fields
        ]
        metrics = [
            {
                "ref": f"metric.{m.key}",
                "label": m.label,
                "type": "decimal",
                "role": "measure",
                "entity": "Metrics",
                "description": m.description or f"Canonical metric ({m.kind})",
                "allowed_aggregations": [],  # already aggregated — drop in as-is
                "is_metric": True,
                "unit": m.unit,
                "certified": m.certified,  # governance: prefer certified metrics
            }
            for m in self.metrics
        ]
        return fields + metrics

    def metadata_for_builder(self) -> list[dict]:
        """Metadata projection for the HUMAN field picker (Document Studio "Make
        dynamic" / insert-field). Same shape as `metadata_for_ai()` plus two
        disambiguating signals a trusted builder-role human can see but the AI
        never should: real sample values (never for a `pii` field), and whether
        the field's entity is the Employee anchor — the live, current mart every
        report joins against, and so almost always the right default when the
        same label appears on more than one entity (e.g. "Designation" on both
        Employee and a historical Promotion History mart)."""
        anchor_key = self.entities[0].key if self.entities else None
        identity_ref = self.record_identity_ref()
        fields = [
            {
                "ref": f.ref,
                "label": f.label,
                "type": f.type.value,
                "role": f.role.value,
                "entity": e.name,
                "description": f.description or f"{e.name}'s {f.label}",
                "allowed_aggregations": [a.value for a in f.allowed_aggregations],
                "sample_values": [] if f.pii else (f.sample_values or [])[:5],
                "is_anchor": e.key == anchor_key,
                "is_record_key": f.ref == identity_ref,
            }
            for e in self.entities
            for f in e.fields
        ]
        metrics = [
            {
                "ref": f"metric.{m.key}",
                "label": m.label,
                "type": "decimal",
                "role": "measure",
                "entity": "Metrics",
                "description": m.description or f"Canonical metric ({m.kind})",
                "allowed_aggregations": [],
                "is_metric": True,
                "unit": m.unit,
                "certified": m.certified,
                "sample_values": [],
                "is_anchor": False,
                "is_record_key": False,
            }
            for m in self.metrics
        ]
        return fields + metrics

    def glossary_for_ai(self) -> list[dict]:
        """Compact term -> definition -> ref list, used to ground the AI in the
        tenant's authoritative business vocabulary (no physical names, no data)."""
        return [
            {"term": t.term, "definition": t.definition, "ref": t.ref,
             "aliases": t.aliases, "category": t.category}
            for t in self.glossary
        ]
