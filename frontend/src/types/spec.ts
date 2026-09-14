// TS types mirroring the backend Pydantic spec models (README §10 gotcha:
// keep this file in lock-step with backend/app/domain/report_spec.py &
// semantic.py so both sides of the wire agree). NO localStorage assumptions.

export type FilterOp =
  | "eq" | "neq" | "gt" | "lt" | "gte" | "lte"
  | "between" | "in" | "contains" | "is_null" | "is_not_null";

export type AggFn = "sum" | "avg" | "count" | "count_distinct" | "min" | "max";
export type SortDir = "asc" | "desc";
export type FieldType = "string" | "integer" | "decimal" | "boolean" | "date" | "datetime";
export type FieldRole = "dimension" | "measure";
export type ParamType = "string" | "number" | "date" | "date_range" | "boolean" | "enum";
export type ExportFormat = "xlsx" | "pdf";

// ── data_spec ───────────────────────────────────────────────────────────
export interface FieldSelection { ref: string; label?: string; agg?: AggFn | null; total?: boolean; source_header?: string; }
export interface FilterClause {
  ref: string; op: FilterOp; value?: unknown; param?: string | null;
}
export interface AggregationSpec { ref: string; fn: AggFn; label?: string; }
export interface SortSpec { ref: string; dir: SortDir; }
export interface CalcCase { ref: string; op: FilterOp; value: unknown; label: string; }
export interface LookupSpec {
  on: string;                        // the ref whose value is translated
  map: Record<string, string>;       // source value -> output label
  default?: string | null;           // label when no key matches
}
export interface CalculatedField {
  name: string;
  label: string;
  expression?: string | null;   // FORMULA: arithmetic over refs
  cases?: CalcCase[];           // BANDING: CASE WHEN … THEN label
  else_label?: string | null;
  lookup?: LookupSpec | null;   // LOOKUP: value -> label mapping table
}
export interface RuntimeParam {
  name: string; type: ParamType; required: boolean;
  label?: string; default?: unknown; enum_values?: string[];
}
export interface UnpivotSpec {
  measures: string[];          // refs to turn into rows
  label_header: string;        // e.g. "Transaction Name"
  value_header: string;        // e.g. "Amount"
  count_header?: string | null; // e.g. "Number of Employees" (optional)
  agg: AggFn;
}
export interface DataSpec {
  entity: string;
  fields: FieldSelection[];
  filters: FilterClause[];
  group_by: string[];
  aggregations: AggregationSpec[];
  calculated_fields: CalculatedField[];
  sort: SortSpec[];
  runtime_params: RuntimeParam[];
  unpivot?: UnpivotSpec | null;
}

// ── presentation_spec ───────────────────────────────────────────────────
export interface Branding { logo_id?: string | null; header?: string | null; footer?: string | null; }
export interface ColumnPresentation {
  ref: string; width?: number | null; format?: string | null;
  align?: string | null; label?: string | null;
}
export interface ConditionalFormat { ref: string; when: FilterOp; value: unknown; style: string; }
export interface PageSetup { orientation: string; totals: boolean; }
export interface PresentationSpec {
  title: string; branding: Branding; columns: ColumnPresentation[];
  conditional_formats: ConditionalFormat[]; page: PageSetup;
  allowed_formats?: string[]; // which outputs the viewer offers: view | excel | pdf
}

// ── semantic layer (metadata-only field shape returned by /semantic/fields) ─
export interface SemanticFieldMeta {
  ref: string; label: string; type: FieldType; role: FieldRole;
  entity: string; description?: string | null; allowed_aggregations: AggFn[];
  // Only present from /semantic/fields/builder (the human field picker) —
  // never sent to the AI. See SemanticCatalog.metadata_for_builder().
  sample_values?: string[]; is_anchor?: boolean; is_record_key?: boolean;
}

// ── query result ────────────────────────────────────────────────────────
export interface RunProvenance {
  run_id: string | null;
  semantic_version_ref: number | null;
  compiled_sql_hash: string | null;
  result_checksum: string | null;
  datamart_snapshot_ref: string | null;
}

export interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  provenance?: RunProvenance; // WS-1 run lineage
}

export const emptyDataSpec = (entity = "employee"): DataSpec => ({
  entity, fields: [], filters: [], group_by: [], aggregations: [],
  calculated_fields: [], sort: [], runtime_params: [],
});

export const emptyPresentation = (title = ""): PresentationSpec => ({
  title,
  branding: { footer: "Confidential" },
  columns: [], conditional_formats: [],
  page: { orientation: "portrait", totals: false },
  allowed_formats: ["view", "excel", "pdf"],
});
