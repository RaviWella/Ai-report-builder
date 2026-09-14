// TS mirror of app/domain/semantic.py MetricDef / MetricFilter.
export interface MetricFilter { ref: string; op: string; value: unknown; }

export interface MetricDef {
  key: string;
  label: string;
  description?: string | null;
  unit?: string | null; // currency | count | percent | number
  kind: "aggregate" | "count" | "formula";
  agg?: string | null;  // sum | avg | min | max (aggregate)
  ref?: string | null;  // measure ref (aggregate) | count target
  distinct?: boolean;
  expression?: string | null; // formula over metric.<key>
  filters?: MetricFilter[];
  aliases?: string[];
  source?: string; // seed | introspected | custom
}
