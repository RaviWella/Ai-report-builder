/**
 * Client-side CSV export for HR report tables.
 */

export type HrCsvColumn<T extends object> = {
  key: keyof T | string;
  header: string;
  value?: (row: T) => unknown;
};

function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const s = String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function cellValue<T extends object>(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key];
}

export function exportHrRowsToCsv<T extends object>(
  columns: HrCsvColumn<T>[],
  rows: T[],
  filename: string,
): void {
  if (!columns.length || !rows.length) return;

  const lines = [
    columns.map((c) => escapeCsvCell(c.header)).join(","),
    ...rows.map((row) =>
      columns
        .map((col) => {
          const raw = col.value
            ? col.value(row)
            : cellValue(row, String(col.key));
          return escapeCsvCell(raw);
        })
        .join(","),
    ),
  ];

  const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function sanitizeCsvFilenamePart(value: string): string {
  return value.replace(/[^\w.-]+/g, "_").replace(/^_|_$/g, "") || "report";
}

/** Build export filename from the report display label (matches backend custom report naming). */
export function buildCustomReportExportFilename(
  label: string,
  format: "xlsx" | "pdf",
  filters?: {
    proc_year?: number;
    proc_month?: number;
    emp_no?: string;
    column_filters?: Record<string, string[]>;
  },
): string {
  let safe = label.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_");
  if (!safe) safe = "report";
  if (filters?.proc_year != null && filters?.proc_month != null) {
    const month = String(filters.proc_month).padStart(2, "0");
    safe = `${safe}_${filters.proc_year}-${month}`;
  }
  if (filters?.emp_no) {
    const emp = String(filters.emp_no).replace(/[^\w-]/g, "");
    if (emp) safe = `${safe}_${emp}`;
  }
  if (
    filters?.column_filters &&
    Object.values(filters.column_filters).some((values) => values.length > 0)
  ) {
    safe = `${safe}_filtered`;
  }
  return `${safe}.${format}`;
}

/** Fetch every page when the API caps page size (e.g. 500). */
export async function fetchAllHrPages<T>(options: {
  total: number;
  pageSize: number;
  fetchPage: (offset: number, limit: number) => Promise<{ items: T[] }>;
}): Promise<T[]> {
  const { total, pageSize, fetchPage } = options;
  if (total <= 0) return [];

  const all: T[] = [];
  for (let offset = 0; offset < total; offset += pageSize) {
    const limit = Math.min(pageSize, total - offset);
    const page = await fetchPage(offset, limit);
    all.push(...page.items);
    if (page.items.length < limit) break;
  }
  return all;
}
