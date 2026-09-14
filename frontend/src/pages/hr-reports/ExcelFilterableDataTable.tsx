import { useState } from "react";
import { Filter } from "lucide-react";
import ExcelColumnFilterMenu from "./ExcelColumnFilterMenu";
import {
  appliedValuesForColumn,
  clearColumnFilter,
  columnFilterLabel,
  commitColumnSelection,
  isColumnFilterActive,
  type ColumnFilterState,
} from "./columnFilterUtils";
import { formatReportCellValue, isReportAmountColumn } from "../../lib/reportAmountFormat";
import type { ColumnFilterOption } from "../../services/api";

interface ColumnDef {
  key: string;
  header: string;
}

interface ExcelFilterableDataTableProps {
  columns: ColumnDef[];
  rows: Record<string, unknown>[];
  filterableColumns?: string[];
  filterOptions: ColumnFilterOption[];
  columnFilters: ColumnFilterState;
  onColumnFiltersChange: (filters: ColumnFilterState) => void;
  onRequestFilterValues?: (column: string) => void | Promise<void>;
  loadingFilterColumn?: string | null;
  emptyMessage?: string;
  disabled?: boolean;
  /** Override scroll/height on the table wrapper (default: horizontal scroll only). */
  wrapperClassName?: string;
  /** Keep column headers visible while scrolling (page or container scroll). */
  stickyHeader?: boolean;
}

function cellDisplay(column: string, value: unknown) {
  return formatReportCellValue(column, value);
}

export default function ExcelFilterableDataTable({
  columns,
  rows,
  filterableColumns,
  filterOptions,
  columnFilters,
  onColumnFiltersChange,
  onRequestFilterValues,
  loadingFilterColumn = null,
  emptyMessage = "No data available.",
  disabled = false,
  wrapperClassName = "overflow-x-auto",
  stickyHeader = false,
}: ExcelFilterableDataTableProps) {
  const [openFilterColumn, setOpenFilterColumn] = useState<string | null>(null);

  const optionsByColumn = Object.fromEntries(
    filterOptions.map((option) => [option.column, option.values]),
  );
  const filterableSet = new Set(filterableColumns ?? filterOptions.map((o) => o.column));

  if (!columns.length) {
    return (
      <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className={`rounded-xl border border-slate-200 bg-white ${wrapperClassName}`}>
      <table className="min-w-full text-sm">
        <thead className={stickyHeader ? "sticky top-0 z-10 bg-slate-50 shadow-[inset_0_-1px_0_rgb(226_232_240)]" : undefined}>
          <tr className="border-b border-slate-200 bg-slate-50">
            {columns.map((col) => {
              const filterActive = isColumnFilterActive(col.key, columnFilters);
              const allValues = optionsByColumn[col.key] ?? [];
              const canFilter = filterableSet.has(col.key);
              const menuOpen = openFilterColumn === col.key;
              const valuesLoading = loadingFilterColumn === col.key;

              return (
                <th
                  key={col.key}
                  className="relative whitespace-nowrap px-4 py-2.5 text-left font-bold text-slate-700"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="capitalize">{col.header}</span>
                    {canFilter && (
                      <button
                        type="button"
                        disabled={disabled}
                        onClick={() => {
                          const nextOpen = menuOpen ? null : col.key;
                          setOpenFilterColumn(nextOpen);
                          if (nextOpen && onRequestFilterValues) {
                            void onRequestFilterValues(nextOpen);
                          }
                        }}
                        className={`rounded p-0.5 transition-colors hover:bg-slate-200 disabled:opacity-40 ${
                          filterActive ? "text-teal-600" : "text-slate-400"
                        }`}
                        aria-label={`Filter ${col.header}`}
                        aria-expanded={menuOpen}
                        title="Column filter"
                      >
                        <Filter size={14} className={filterActive ? "fill-current" : ""} />
                      </button>
                    )}
                  </div>
                  {menuOpen && canFilter && (
                    <ExcelColumnFilterMenu
                      column={col.key}
                      values={allValues}
                      loading={valuesLoading}
                      initialSelected={appliedValuesForColumn(
                        col.key,
                        allValues,
                        columnFilters,
                      )}
                      onApply={(selected) =>
                        onColumnFiltersChange(
                          commitColumnSelection(
                            col.key,
                            allValues,
                            selected,
                            columnFilters,
                          ),
                        )
                      }
                      onClear={() =>
                        onColumnFiltersChange(clearColumnFilter(col.key, columnFilters))
                      }
                      onClose={() => setOpenFilterColumn(null)}
                    />
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {!rows.length ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-10 text-center text-sm text-slate-500"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50/80"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`whitespace-nowrap px-4 py-2.5 text-slate-700 ${
                      isReportAmountColumn(col.key) ? "text-right tabular-nums" : ""
                    }`}
                  >
                    {cellDisplay(col.key, row[col.key])}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function ActiveColumnFilterBar({
  columnFilters,
  onColumnFiltersChange,
  disabled,
}: {
  columnFilters: ColumnFilterState;
  onColumnFiltersChange: (filters: ColumnFilterState) => void;
  disabled?: boolean;
}) {
  const activeEntries = Object.entries(columnFilters).filter(([, values]) => values.length > 0);
  if (!activeEntries.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-teal-100 bg-teal-50/50 px-3 py-2 text-xs">
      <span className="font-medium text-teal-900">Filtered by:</span>
      {activeEntries.map(([column, values]) => (
        <button
          key={column}
          type="button"
          disabled={disabled}
          onClick={() => onColumnFiltersChange(clearColumnFilter(column, columnFilters))}
          className="inline-flex max-w-xs items-center gap-1 rounded-full border border-teal-200 bg-white px-2.5 py-0.5 text-teal-800 hover:bg-teal-50 disabled:opacity-50"
          title="Click to remove this filter"
        >
          <span className="font-medium capitalize">{columnFilterLabel(column)}:</span>
          <span className="truncate">
            {values.length > 2
              ? `${values.slice(0, 2).join(", ")} +${values.length - 2}`
              : values.join(", ")}
          </span>
          <span aria-hidden className="text-teal-500">
            ×
          </span>
        </button>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onColumnFiltersChange({})}
        className="ml-1 font-medium text-teal-700 underline-offset-2 hover:underline disabled:opacity-50"
      >
        Clear all
      </button>
    </div>
  );
}
