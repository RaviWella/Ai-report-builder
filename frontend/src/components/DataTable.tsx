import type { ReactNode } from "react";

interface Column<T> {
  key: keyof T | string;
  header: string;
  align?: "left" | "right";
  render?: (row: T) => React.ReactNode;
}

interface DataTableProps<T extends object> {
  columns: Column<T>[];
  rows: T[];
  emptyMessage?: string;
  /** Rich empty state with next-step copy and links. Takes precedence over emptyMessage. */
  emptyContent?: ReactNode;
  /** Override scroll on the table wrapper (default: horizontal scroll only). */
  wrapperClassName?: string;
  /** Keep column headers visible while scrolling. */
  stickyHeader?: boolean;
}

function cellValue<T extends object>(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key];
}

export default function DataTable<T extends object>({
  columns,
  rows,
  emptyMessage = "No data available.",
  emptyContent,
  wrapperClassName = "overflow-x-auto -mx-px sm:mx-0",
  stickyHeader = false,
}: DataTableProps<T>) {
  if (!rows.length) {
    if (emptyContent) return <>{emptyContent}</>;
    return (
      <p className="text-sm text-slate-500 bg-white border border-slate-200 rounded-xl p-8 text-center">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className={`bg-white border border-slate-200 rounded-xl ${wrapperClassName}`}>
      <table className="min-w-full text-sm">
        <thead className={stickyHeader ? "sticky top-0 z-10 bg-slate-50 shadow-[inset_0_-1px_0_rgb(226_232_240)]" : undefined}>
          <tr className="border-b border-slate-200 bg-slate-50">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={`px-4 py-3 font-semibold text-slate-600 ${
                  col.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-slate-100 last:border-0 hover:bg-slate-50/80"
            >
              {columns.map((col) => (
                <td
                  key={String(col.key)}
                  className={`px-4 py-2.5 text-slate-700 ${
                    col.align === "right" ? "text-right tabular-nums" : ""
                  }`}
                >
                  {col.render
                    ? col.render(row)
                    : String(cellValue(row, String(col.key)) ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
