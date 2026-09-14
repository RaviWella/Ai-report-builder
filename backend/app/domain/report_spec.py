"""Report definition models (README §6, SRS §6).

A template version stores TWO JSONB blobs, kept separate so presentation can
change without rebuilding the query and vice-versa:
  - DataSpec          -> drives the Query Engine
  - PresentationSpec  -> drives the Rendering Engine

The spec is the source of truth; SQL is a compiled artifact (D4). `ref` values are
ALWAYS semantic-layer references, never physical names. Runtime filter values are
bound parameters, never inlined.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import AggFn, FilterOp, ParamType, SortDir


# --------------------------------------------------------------------------- #
# data_spec
# --------------------------------------------------------------------------- #
class FieldSelection(BaseModel):
    ref: str
    label: str | None = None
    agg: AggFn | None = None  # non-null => this selection is aggregated
    total: bool = False  # show a SUM of this column in the totals row (Excel/PDF)
    source_header: str | None = None  # the Excel heading this column was mapped from


class FilterClause(BaseModel):
    """A filter. EITHER a static `value` (builder-fixed) OR a `param` name that is
    bound at run-time from runtime_params (FR-V3 / security §7.2). Never both."""

    ref: str
    op: FilterOp
    value: Any | None = None
    param: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "FilterClause":
        no_arg = self.op in (FilterOp.IS_NULL, FilterOp.IS_NOT_NULL)
        if no_arg:
            return self
        has_value = self.value is not None
        has_param = self.param is not None
        if has_value == has_param:  # both or neither
            raise ValueError(
                f"Filter on {self.ref!r} must set exactly one of 'value' or 'param'"
            )
        return self


class AggregationSpec(BaseModel):
    ref: str
    fn: AggFn
    label: str | None = None


class SortSpec(BaseModel):
    ref: str
    dir: SortDir = SortDir.ASC


class UnpivotSpec(BaseModel):
    """Turn selected MEASURES into ROWS — one row per measure: its label, the
    aggregated value and (optionally) a count of rows where it is non-zero.
    Generic: the caller picks the measures, labels come from the semantic layer,
    the engine emits a UNION of per-measure aggregates. Powers Grand-Summary-style
    reports from ANY wide entity without report-specific code."""

    measures: list[str] = Field(default_factory=list)  # refs to turn into rows
    label_header: str = "Name"     # header for the measure-name column
    value_header: str = "Value"    # header for the aggregated-value column
    count_header: str | None = None  # if set, add a "# rows non-zero" column
    agg: AggFn = AggFn.SUM


class CalcCase(BaseModel):
    """One branch of a banding/CASE derived field: when <ref> <op> <value> -> label."""

    ref: str
    op: FilterOp
    value: Any
    label: str  # output label for this branch (a literal string)


class LookupSpec(BaseModel):
    """A value-mapping derived field: read `on` (a semantic ref) and translate each
    value through `map` (source value -> output label), falling back to `default`.

    e.g. on="employee.grade", map={"A": "Senior", "B": "Mid"}, default="Other".
    Compiled to a safe CASE (equality per key); keys and labels are bound literals,
    never raw SQL. Keys are matched as text so mixed source types are handled."""

    on: str  # the semantic ref whose value is translated
    map: dict[str, str] = Field(default_factory=dict)
    default: str | None = None  # label when no key matches


class CalculatedField(BaseModel):
    """Derived field (FR-B5). Governed kinds only — never raw SQL, never eval'd:

    - FORMULA: `expression` is arithmetic (+ - * /) over other refs, e.g.
      "payroll.gross - payroll.deductions". Compiled to a safe SQLAlchemy expr.
    - BANDING: `cases` is an ordered CASE WHEN list producing a text label, e.g.
      Age < 20 -> "Under 20"; with `else_label` as the fallback.
    - LOOKUP: `lookup` maps the values of one ref onto labels (a mapping table),
      e.g. grade A -> "Senior"; with `lookup.default` as the fallback.

    Exactly one of `expression` / `cases` / `lookup` is set. Exposed as "calc.<name>"."""

    name: str  # new virtual ref suffix, exposed as "calc.<name>"
    label: str
    expression: str | None = None  # e.g. "payroll.gross - payroll.deductions"
    cases: list[CalcCase] = Field(default_factory=list)
    else_label: str | None = None
    lookup: LookupSpec | None = None

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> "CalculatedField":
        kinds = [bool(self.expression and self.expression.strip()),
                 bool(self.cases), bool(self.lookup and self.lookup.map)]
        if sum(kinds) != 1:
            raise ValueError(
                f"Calculated field {self.name!r} must set exactly one of "
                f"'expression', 'cases' or 'lookup' (with a non-empty map)"
            )
        return self


class RuntimeParam(BaseModel):
    name: str
    type: ParamType
    required: bool = False
    label: str | None = None
    default: Any | None = None
    enum_values: list[str] | None = None


class DataSpec(BaseModel):
    entity: str  # root entity key, e.g. "employee"
    fields: list[FieldSelection] = Field(default_factory=list)
    filters: list[FilterClause] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[AggregationSpec] = Field(default_factory=list)
    calculated_fields: list[CalculatedField] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    runtime_params: list[RuntimeParam] = Field(default_factory=list)
    unpivot: UnpivotSpec | None = None  # summary/grand-total mode (measures -> rows)

    def all_refs(self) -> set[str]:
        refs: set[str] = {f.ref for f in self.fields}
        refs |= {f.ref for f in self.filters}
        refs |= set(self.group_by)
        refs |= {a.ref for a in self.aggregations}
        refs |= {s.ref for s in self.sort}
        if self.unpivot:
            refs |= set(self.unpivot.measures)
        return refs


# --------------------------------------------------------------------------- #
# presentation_spec
# --------------------------------------------------------------------------- #
class Branding(BaseModel):
    logo_id: str | None = None
    header: str | None = None
    footer: str | None = "Confidential"


class ColumnPresentation(BaseModel):
    ref: str
    width: int | None = None
    format: str | None = None  # "currency" | "percentage" | "date" | "number:2" ...
    align: str | None = None  # "left" | "right" | "center"
    label: str | None = None


class ConditionalFormat(BaseModel):
    ref: str
    when: FilterOp
    value: Any
    style: str  # named style, e.g. "highlight" | "red_text"


class PageSetup(BaseModel):
    orientation: str = "portrait"  # portrait | landscape
    totals: bool = False


class PivotSpec(BaseModel):
    """Reshape a long (rule-report) result — one row per e.g. (employee, date)
    — into a wide grid: one row per identity (every OTHER output column),
    one column per DISTINCT value of `column_field` actually present in the
    result (so the column set is driven by the data/filters at run time, not
    fixed at authoring time — a date-range filter naturally yields one column
    per date in range, but `column_field` can be any dimension). A display
    concern applied AFTER the query runs (report_service._apply_pivot) —
    never part of the governed RuleReportSpec/calculation itself."""

    column_field: str                    # output column whose distinct values become columns
    value_field: str                     # output column whose value fills each cell
    status_field: str | None = None      # output column driving each cell's color (optional)
    column_label_format: str | None = None  # strftime format for a date column_field, e.g. "%d %b"
    status_colors: dict[str, str] = Field(default_factory=dict)  # status value -> hex color


class PresentationSpec(BaseModel):
    title: str
    branding: Branding = Field(default_factory=Branding)
    columns: list[ColumnPresentation] = Field(default_factory=list)
    conditional_formats: list[ConditionalFormat] = Field(default_factory=list)
    page: PageSetup = Field(default_factory=PageSetup)
    pivot: PivotSpec | None = None
    # Which outputs the viewer offers for this report. A builder can switch any
    # off (e.g. a sensitive report = "view only"). Defaults to all three for
    # tabular reports; payslips default to ["pdf"] (set in the payslip envelope).
    allowed_formats: list[str] = Field(default_factory=lambda: ["view", "excel", "pdf"])


# --------------------------------------------------------------------------- #
# combined definition (what one immutable version snapshots)
# --------------------------------------------------------------------------- #
class ReportDefinition(BaseModel):
    """Both specs together — correctness depends on their combination (SRS §7.2)."""

    data_spec: DataSpec
    presentation_spec: PresentationSpec
