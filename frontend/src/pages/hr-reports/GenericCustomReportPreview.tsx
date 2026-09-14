import { useEffect, useMemo, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import PeriodFilter from "../../components/PeriodFilter";
import ReportQueryError from "../../components/ReportQueryError";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import { viewSupportsPayrollPeriodFilter } from "../../lib/payrollReportPeriodConfig";
import CustomReportExportButtons from "./CustomReportExportButtons";
import CustomReportPreviewHeader from "./CustomReportPreviewHeader";
import ExcelFilterableDataTable, {
  ActiveColumnFilterBar,
} from "./ExcelFilterableDataTable";
import { ReportTableSkeleton } from "../../components/ReportLoadingSkeleton";
import TablePagination from "../../components/TablePagination";
import {
  formatReportColumnLabel,
  hasActiveColumnFilters,
  serializeColumnFilters,
  type ColumnFilterState,
} from "./columnFilterUtils";
import { parsePeriodKey } from "./customReportPeriod";
import {
  getErrorMessage,
  hrApi,
  type CustomReportView,
} from "../../services/api";

const PAGE_SIZE = 50;

type ExportFormat = "xlsx" | "pdf";

interface GenericCustomReportPreviewProps {
  view: CustomReportView;
}

export default function GenericCustomReportPreview({ view }: GenericCustomReportPreviewProps) {
  const [page, setPage] = useState(0);
  const [columnFilters, setColumnFilters] = useState<ColumnFilterState>({});
  const [loadedFilterValues, setLoadedFilterValues] = useState<Record<string, string[]>>({});
  const [loadingFilterColumn, setLoadingFilterColumn] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<ExportFormat | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const usesPeriodFilter = viewSupportsPayrollPeriodFilter(view);
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const periodParts = useMemo(
    () => (period ? parsePeriodKey(period) : null),
    [period],
  );

  const columnFiltersParam = useMemo(
    () => serializeColumnFilters(columnFilters),
    [columnFilters],
  );

  useEffect(() => {
    setPage(0);
    setColumnFilters({});
    setLoadedFilterValues({});
    setExportError(null);
  }, [view.view_name]);

  useEffect(() => {
    setPage(0);
  }, [columnFiltersParam, period]);

  const {
    data: filterOptions,
    isLoading: filtersLoading,
    isError: filtersOptionsError,
    error: filtersOptionsLoadError,
  } = useQuery({
    queryKey: ["custom-report-column-filters", view.view_name],
    queryFn: () => hrApi.listColumnFilters(view.view_name),
    staleTime: 5 * 60 * 1000,
  });

  const filterableColumns = useMemo(
    () => filterOptions?.columns.map((option) => option.column) ?? [],
    [filterOptions],
  );

  const requestFilterValues = useCallback(
    async (column: string) => {
      if (column in loadedFilterValues) return;
      setLoadingFilterColumn(column);
      try {
        const response = await hrApi.listColumnFilters(view.view_name, column);
        const values =
          response.columns.find((item) => item.column === column)?.values ?? [];
        setLoadedFilterValues((prev) => ({ ...prev, [column]: values }));
      } catch (err) {
        setExportError(getErrorMessage(err));
      } finally {
        setLoadingFilterColumn(null);
      }
    },
    [loadedFilterValues, view.view_name],
  );

  const filterOptionsList = useMemo(
    () =>
      filterableColumns.map((column) => ({
        column,
        values: loadedFilterValues[column] ?? [],
      })),
    [filterableColumns, loadedFilterValues],
  );

  const offset = page * PAGE_SIZE;

  const previewReady = !usesPeriodFilter || !!periodParts;

  const { data, isLoading, isFetching, isError, error, refetch, isRefetching } = useQuery({
    queryKey: [
      "custom-report-preview",
      view.view_name,
      page,
      columnFiltersParam,
      periodParts?.proc_year,
      periodParts?.proc_month,
    ],
    queryFn: () =>
      hrApi.previewCustomReport(view.view_name, {
        limit: PAGE_SIZE,
        offset,
        ...(usesPeriodFilter && periodParts ? periodParts : {}),
        ...(columnFiltersParam ? { column_filters: columnFiltersParam } : {}),
      }),
    enabled: previewReady,
    placeholderData: (prev) => prev,
  });

  async function handleDownload(format: ExportFormat) {
    setExportError(null);
    setDownloading(format);
    try {
      await hrApi.downloadCustomReport(
        view.view_name,
        format,
        {
          ...(usesPeriodFilter && periodParts ? periodParts : {}),
          column_filters: columnFilters,
        },
        view.label,
      );
    } catch (err) {
      setExportError(getErrorMessage(err));
    } finally {
      setDownloading(null);
    }
  }

  const columns =
    data?.columns.map((column) => ({
      key: column,
      header: formatReportColumnLabel(column),
    })) ?? [];

  const exportBusy = downloading !== null;
  const tableBusy = exportBusy || isFetching || filtersLoading;

  const subtitle = usesPeriodFilter
    ? data
      ? `Payroll period ${period} · ${data.total.toLocaleString()} row${data.total === 1 ? "" : "s"} · use column filters for more`
      : "Select a payroll period, then refine with column header filters"
    : data
      ? `Click the filter icon in a column header to filter · ${data.total.toLocaleString()} row${data.total === 1 ? "" : "s"}`
      : "Click the filter icon in a column header to filter like Excel";

  return (
    <div className="hrm-report-page hrm-report-page--spaced space-y-6">
      <CustomReportPreviewHeader
        title={view.label}
        subtitle={subtitle}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {usesPeriodFilter && (
              <PeriodFilter
                value={period}
                onChange={setPeriod}
                label="Payroll period"
              />
            )}
            <CustomReportExportButtons
              downloading={downloading}
              disabled={tableBusy || (usesPeriodFilter && (periodLoading || !period))}
              onDownload={handleDownload}
            />
          </div>
        }
      />

      {exportError && (
        <ReportQueryError title="Export failed" message={exportError} />
      )}

      {filtersOptionsError && (
        <ReportQueryError
          title="Could not load column filters"
          message={getErrorMessage(filtersOptionsLoadError)}
        />
      )}

      <ActiveColumnFilterBar
        columnFilters={columnFilters}
        onColumnFiltersChange={setColumnFilters}
        disabled={tableBusy}
      />

      <section>
        <h2 className="hrm-report-section-title mb-3">
          Preview
        </h2>

        {usesPeriodFilter && periodLoading ? (
          <ReportTableSkeleton rows={8} />
        ) : usesPeriodFilter && !period ? (
          <p className="text-sm text-slate-600">Select a payroll period to load the preview.</p>
        ) : isLoading && !data ? (
          <ReportTableSkeleton rows={8} />
        ) : isError ? (
          <ReportQueryError
            title="Could not load preview"
            message={getErrorMessage(error)}
            onRetry={() => void refetch()}
            retrying={isRefetching}
          />
        ) : (
          <div className={`space-y-3 ${isFetching ? "pointer-events-none opacity-60" : ""}`}>
            <ExcelFilterableDataTable
              columns={columns}
              rows={data?.rows ?? []}
              filterableColumns={filterableColumns}
              filterOptions={filterOptionsList}
              columnFilters={columnFilters}
              onColumnFiltersChange={setColumnFilters}
              onRequestFilterValues={requestFilterValues}
              loadingFilterColumn={loadingFilterColumn}
              disabled={tableBusy}
              stickyHeader
              emptyMessage={
                hasActiveColumnFilters(columnFilters)
                  ? "No rows match the selected column filters."
                  : "This report view has no rows."
              }
            />
            {isFetching && (
              <div className="flex items-center gap-2 text-xs text-slate-600" aria-live="polite">
                <Loader2 size={12} className="hrm-table-toolbar__spin" aria-hidden />
                Updating preview…
              </div>
            )}
            {data && data.total > 0 && (
              <TablePagination
                total={data.total}
                limit={PAGE_SIZE}
                offset={offset}
                onPageChange={setPage}
                disabled={tableBusy}
              />
            )}
          </div>
        )}
      </section>
    </div>
  );
}
