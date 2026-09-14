export type ColumnFilterState = Record<string, string[]>;

export function serializeColumnFilters(filters: ColumnFilterState): string | undefined {
  const active = Object.fromEntries(
    Object.entries(filters).filter(([, values]) => values.length > 0),
  );
  return Object.keys(active).length > 0 ? JSON.stringify(active) : undefined;
}

const REPORT_LABEL_ACRONYMS: Record<string, string> = {
  ot: "OT",
  je: "JE",
};

const REPORT_COLUMN_LABEL_OVERRIDES: Record<string, string> = {
  proc_year: "Year",
  proc_month: "Month",
  reporting_year: "Year",
  reporting_month: "Month",
};

function formatLabelWord(part: string): string {
  const lower = part.toLowerCase();
  if (lower in REPORT_LABEL_ACRONYMS) return REPORT_LABEL_ACRONYMS[lower];
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/** Human-readable report column heading (underscores → spaces, known acronyms preserved). */
export function formatReportColumnLabel(column: string): string {
  const override = REPORT_COLUMN_LABEL_OVERRIDES[column.toLowerCase()];
  if (override) return override;
  return column
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map(formatLabelWord)
    .join(" ");
}

export function columnFilterLabel(column: string) {
  return formatReportColumnLabel(column);
}

export function hasActiveColumnFilters(filters: ColumnFilterState) {
  return Object.values(filters).some((values) => values.length > 0);
}

export function isColumnFilterActive(column: string, filters: ColumnFilterState) {
  return (filters[column]?.length ?? 0) > 0;
}

/** Values currently applied for a column, or all values when no filter is set. */
export function appliedValuesForColumn(
  column: string,
  allValues: string[],
  filters: ColumnFilterState,
): string[] {
  const selected = filters[column];
  if (!selected?.length) return allValues;
  return selected;
}

/** Commit checkbox selection: all selected => no filter; subset => filter. */
export function commitColumnSelection(
  column: string,
  allValues: string[],
  checked: string[],
  filters: ColumnFilterState,
): ColumnFilterState {
  const next = { ...filters };
  if (checked.length === 0) {
    next[column] = [];
    return next;
  }
  if (checked.length >= allValues.length) {
    delete next[column];
    return next;
  }
  next[column] = checked;
  return next;
}

export function clearColumnFilter(
  column: string,
  filters: ColumnFilterState,
): ColumnFilterState {
  const next = { ...filters };
  delete next[column];
  return next;
}

export function clearAllColumnFilters(): ColumnFilterState {
  return {};
}
