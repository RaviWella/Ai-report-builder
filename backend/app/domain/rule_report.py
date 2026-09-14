"""Rule-report spec — a governed, declarative calculation report (SRS §4.x).

Some client reports are too rule-heavy for the visual builder's field/filter/
formula primitives (e.g. an Overtime report that classifies each day into a type,
applies a per-type qualifying-hours rule, rolls up to a month, and compares against
an NPL-adjusted threshold). Instead of hand-writing SQL per client, the rules are
expressed as a DECLARATIVE JSON spec that a governed engine compiles to safe SQL.

Nothing here is raw SQL and nothing is eval'd: the string expressions (`when`,
`value`, rollup/compute formulas) are parsed by a whitelisted expression compiler
(see app/query_engine/rule_compiler.py) into parameterised SQLAlchemy — the same
safety model as calculated fields.

Shape (mirrors the shape validated against the Golden Key OT report):

    RuleReportSpec
      source        "mart.mart_attendance_daily"    -- the per-row (daily) grain
      grain         ["employee_no", "year_month"]   -- group-by keys for the rollup
      constants     {min_per_day: 6, ph: 8, ...}    -- per-tenant policy numbers
      day_value     define + cases[when→value] + else  -- the per-row derived number
      rollup        {total: "sum(day_value)", ...}  -- aggregations over the grain
      compute       {ot: "max(0, total - min)", ...}-- formulas over rollup results
      output        [ ...column names... ]
      filters       [ {name,type,required}, ... ]   -- runtime params
"""

from __future__ import annotations

import re

from pydantic import AliasChoices, BaseModel, Field, model_validator

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class RuleCase(BaseModel):
    """One branch of the per-row day-value classification: when <cond> → <value>.

    `when` is a boolean expression over source columns / defines / flags; `value`
    is an arithmetic expression producing the row's contribution. First match wins."""

    when: str
    value: str


class RuleDayValue(BaseModel):
    """The per-row derived value (e.g. a day's qualifying hours).

    `define` names reusable sub-expressions (e.g. adj_worked); `cases` is an ordered
    when→value list; `else_value` is the fallback when no case matches."""

    define: dict[str, str] = Field(default_factory=dict)
    cases: list[RuleCase] = Field(default_factory=list)
    else_value: str | None = Field(default=None, alias="else")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _needs_cases(self) -> "RuleDayValue":
        if not self.cases:
            raise ValueError("day_value must have at least one case")
        return self


class RuleRowCases(BaseModel):
    """An extra labeled per-row derivation (e.g. a `day_category` tag), evaluated
    alongside `day_value` over the same source/define namespace. Its output column
    is available to `rollup` — typically for FILTER breakdowns
    (`sum(day_value) where day_category == 'normal'`). First match wins; `else_value`
    is the fallback."""

    cases: list[RuleCase] = Field(default_factory=list)
    else_value: str | None = Field(default=None, alias="else")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _needs_cases(self) -> "RuleRowCases":
        if not self.cases:
            raise ValueError("row_cases entry must have at least one case")
        return self


class RulePriority(BaseModel):
    """How a `left_pick_one` join chooses THE ONE row to keep per base row: rank by
    `column` following `order` (unlisted values rank last), then `tiebreak` if given."""

    column: str
    order: list[str] = Field(default_factory=list)
    tiebreak: str | None = None
    tiebreak_dir: str = "desc"   # asc | desc

    @model_validator(mode="after")
    def _ok(self) -> "RulePriority":
        if not self.order:
            raise ValueError("priority.order must list at least one value")
        if self.tiebreak_dir not in ("asc", "desc"):
            raise ValueError("priority.tiebreak_dir must be 'asc' or 'desc'")
        return self


class RuleJoin(BaseModel):
    """How a non-base source attaches to the base table.

    `on` is a list of "this_col = base_col" equality keys (identifiers only — never a
    free expression). `type`:
      • left / inner     — plain LEFT/INNER JOIN on the keys (may fan out).
      • left_pick_one    — LEFT JOIN LATERAL that keeps ONE row per base row, chosen by
                           `priority`. Use when the source can have several matching
                           rows per base row (e.g. multiple leaves on a day)."""

    type: str = "left"                       # left | inner | left_pick_one
    on: list[str] = Field(default_factory=list)
    priority: RulePriority | None = None

    @model_validator(mode="after")
    def _ok(self) -> "RuleJoin":
        if self.type not in ("left", "inner", "left_pick_one"):
            raise ValueError(f"join type must be left|inner|left_pick_one, got {self.type!r}")
        if not self.on:
            raise ValueError("join.on must have at least one 'this_col = base_col' key")
        for cond in self.on:
            parts = [p.strip() for p in cond.split("=")]
            if len(parts) != 2 or not all(_NAME_RE.match(p) for p in parts):
                raise ValueError(f"join.on key must be 'this_col = base_col' identifiers: {cond!r}")
        if self.type == "left_pick_one" and self.priority is None:
            raise ValueError("left_pick_one join requires a `priority`")
        return self

    def keys(self) -> list[tuple[str, str]]:
        """[(this_col, base_col), …]."""
        return [tuple(p.strip() for p in cond.split("=")) for cond in self.on]


class RuleSource(BaseModel):
    """One physical table in a multi-source spec. `columns` are the physical columns it
    contributes to the flat column namespace (a column may live in only one source —
    ambiguity is a compile error). The base (driving) source has no `join`.

    `column_aliases`: optionally expose a physical column under a DIFFERENT logical
    name in that flat namespace — e.g. two sources both physically named "work_date"
    (one needed only as a join key, the other as the spec's actual grain/filter
    column) collide otherwise. `{physical_column: logical_name}`. The join's own
    `on` keys always use the PHYSICAL name (joins are wired before aliasing is
    applied) — aliasing only affects what grain/filters/day_value/rollup can refer
    to by name."""

    table: str
    columns: list[str] = Field(default_factory=list)
    join: RuleJoin | None = None
    column_aliases: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ok(self) -> "RuleSource":
        if "." not in self.table:
            raise ValueError(f"source table must be 'schema.table', got {self.table!r}")
        if not self.columns:
            raise ValueError(f"source {self.table!r} must declare its columns")
        unknown = set(self.column_aliases) - set(self.columns)
        if unknown:
            raise ValueError(f"column_aliases keys must be declared columns: {sorted(unknown)}")
        for logical in self.column_aliases.values():
            if not _NAME_RE.match(logical):
                raise ValueError(f"column_aliases value must be a lower_snake identifier: {logical!r}")
        return self


class RuleFilter(BaseModel):
    """A runtime filter/parameter (date range, employee number, department …).

    `column` names the SOURCE column it filters (applied at the per-row level,
    before aggregation) and `op` how — a missing param value is simply not applied.
    `column=None` means the filter is informational (collected but not wired).

    `expose_as`: optionally ALSO project this filter's chosen runtime value as an
    output column (e.g. show the selected "to" date as an "End date" column on
    every row) — the same value used to filter, not a second concept. Reuses the
    existing bound-parameter machinery; unset by default, so specs that don't use
    it (e.g. Golden Key OT) are unaffected."""

    name: str
    type: str = "string"   # string | number | date | period
    required: bool = False
    label: str | None = None
    column: str | None = None
    op: str = "eq"         # eq | neq | gte | lte | gt | lt | contains
    expose_as: str | None = None


class RuleReportSpec(BaseModel):
    """A declarative, governed calculation report compiled to safe SQL.

    Two-level: a per-row `day_value` computed over `source`, then aggregated to
    `grain` via `rollup`, then `compute` derives final metrics over those
    aggregates (using `constants`). Output is `output` columns."""

    name: str
    source: str = ""                                     # single-source: "schema.table"
    sources: dict[str, RuleSource] = Field(default_factory=dict)  # multi-source (first = base)
    joins_note: str = ""                                 # optional human note about the joins
    grain: list[str] = Field(default_factory=list)       # group-by columns
    constants: dict[str, float] = Field(default_factory=dict)
    # The per-row derived value. Canonical name is `row_value` (domain-neutral); the
    # legacy `day_value` is still accepted for specs authored before the rename.
    day_value: RuleDayValue = Field(
        validation_alias=AliasChoices("row_value", "day_value"),
        serialization_alias="row_value",
    )
    row_cases: dict[str, RuleRowCases] = Field(default_factory=dict)  # extra per-row labels (e.g. a category)
    rollup: dict[str, str] = Field(default_factory=dict)   # name -> "agg(expr) [where cond]"
    compute: dict[str, str] = Field(default_factory=dict)  # name -> formula over rollup/constants
    # Post-aggregation row filter (e.g. "count >= 1") — a boolean expression over
    # grain/rollup/compute names, applied BEFORE the row-limit guard so it can't
    # let the limit silently truncate away genuinely-qualifying rows.
    having: str | None = None
    # Final row ordering — grain/rollup/compute names only (never a filter's
    # expose_as column: sorting by a constant is meaningless).
    order_by: list[str] = Field(default_factory=list)
    output: list[str] = Field(default_factory=list)
    filters: list[RuleFilter] = Field(default_factory=list)

    @model_validator(mode="after")
    def _wellformed(self) -> "RuleReportSpec":
        if not _NAME_RE.match(self.name):
            raise ValueError(f"rule report name must be a lower_snake identifier: {self.name!r}")
        # exactly one of `source` (single) or `sources` (multi-source join) is required
        if bool(self.source) == bool(self.sources):
            raise ValueError("provide exactly one of `source` or `sources`")
        if self.source and "." not in self.source:
            raise ValueError(f"source must be 'schema.table', got {self.source!r}")
        if self.sources:
            aliases = list(self.sources)
            for a in aliases:
                if not _NAME_RE.match(a):
                    raise ValueError(f"source alias must be a lower_snake identifier: {a!r}")
            base, *rest = aliases
            if self.sources[base].join is not None:
                raise ValueError(f"the base source {base!r} (first) must not have a `join`")
            for a in rest:
                if self.sources[a].join is None:
                    raise ValueError(f"non-base source {a!r} must have a `join`")
            # NOTE: a column MAY be declared in more than one source (e.g. a shared join
            # key like employee_sk). That is only a problem if such a column is
            # REFERENCED in an expression — the compiler raises then (ambiguous name).
        if not self.grain:
            raise ValueError("grain (group-by columns) is required")
        for key in (*self.rollup, *self.compute, *self.day_value.define, *self.row_cases):
            if not _NAME_RE.match(key):
                raise ValueError(f"derived name must be a lower_snake identifier: {key!r}")
        # compute names must not collide with rollup names (both feed the final row)
        clash = set(self.rollup) & set(self.compute)
        if clash:
            raise ValueError(f"names used in both rollup and compute: {sorted(clash)}")
        # row_cases labels live in the per-row namespace — must not shadow day_value,
        # a define, or a grain column.
        row_clash = set(self.row_cases) & ({"day_value", *self.day_value.define, *self.grain})
        if row_clash:
            raise ValueError(f"row_cases names collide with day_value/define/grain: {sorted(row_clash)}")
        if not self.output:
            raise ValueError("output columns are required")
        exposed = [f.expose_as for f in self.filters if f.expose_as]
        for name in exposed:
            if not _NAME_RE.match(name):
                raise ValueError(f"filter.expose_as must be a lower_snake identifier: {name!r}")
        expose_clash = set(exposed) & (set(self.grain) | set(self.rollup) | set(self.compute))
        if expose_clash:
            raise ValueError(f"filter.expose_as names collide with grain/rollup/compute: {sorted(expose_clash)}")
        order_clash = set(self.order_by) & set(exposed)
        if order_clash:
            raise ValueError(f"order_by may not reference a filter's expose_as column: {sorted(order_clash)}")
        return self

    def derived_names(self) -> set[str]:
        """All names produced by the spec (rollup + compute), available to output."""
        return set(self.rollup) | set(self.compute)
