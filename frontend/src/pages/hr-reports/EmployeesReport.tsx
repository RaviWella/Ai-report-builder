import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import DataTable from "../../components/DataTable";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import ReportTableToolbar from "../../components/ReportTableToolbar";
import { ReportTableSkeleton } from "../../components/ReportLoadingSkeleton";
import TablePagination from "../../components/TablePagination";
import { useToast } from "../../components/ui/Toast";
import {
  exportHrRowsToCsv,
  fetchAllHrPages,
  sanitizeCsvFilenamePart,
} from "../../lib/exportHrTableCsv";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import type { EmployeeRow } from "../../services/api";
import { employeesTableEmpty, reportNoPeriodEmpty } from "./hrReportEmptyStates";
import { formatReportAmount } from "../../lib/reportAmountFormat";
import { EMPLOYEE_TABLE_COLUMNS } from "./employeesReportColumns";

const PAGE_SIZE = 50;
const EXPORT_PAGE_SIZE = 500;

export default function EmployeesReport() {
  const toast = useToast();
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const [page, setPage] = useState(0);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setPage(0);
  }, [period]);

  const offset = page * PAGE_SIZE;

  const { data, isLoading, isFetching, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["employees", period, page],
    queryFn: () =>
      hrApi.getEmployees({
        limit: PAGE_SIZE,
        offset,
        period_label: period,
      }),
    enabled: !!period,
    placeholderData: (prev) => prev,
  });

  const handleExportCsv = useCallback(async () => {
    if (!period || !data?.total) return;
    setExporting(true);
    try {
      const rows = await fetchAllHrPages({
        total: data.total,
        pageSize: EXPORT_PAGE_SIZE,
        fetchPage: (off, limit) =>
          hrApi.getEmployees({ period_label: period, offset: off, limit }),
      });
      exportHrRowsToCsv(
        EMPLOYEE_TABLE_COLUMNS,
        rows,
        `employees-${sanitizeCsvFilenamePart(period)}.csv`,
      );
      toast.success(
        "CSV downloaded",
        `${rows.length.toLocaleString()} employee${rows.length === 1 ? "" : "s"} exported.`,
      );
    } catch (e) {
      toast.error("Export failed", getErrorMessage(e));
    } finally {
      setExporting(false);
    }
  }, [period, data?.total, toast]);

  const description = `${period ? `Roster at month-end ${period}` : "Active roster"}${
    data ? ` · ${data.total.toLocaleString()} employees` : ""
  }`;

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader title="Employees" description={description}>
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <ReportTableSkeleton rows={8} />
      ) : isError ? (
        <ReportQueryError
          title="Could not load employees"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isRefetching}
        />
      ) : (
        <div className="space-y-3">
          <ReportTableToolbar
            onExportCsv={handleExportCsv}
            exporting={exporting}
            exportDisabled={!data?.total}
            exportLabel="Download roster CSV"
          />
          <DataTable<EmployeeRow>
            rows={data?.items ?? []}
            emptyContent={employeesTableEmpty(period)}
            columns={EMPLOYEE_TABLE_COLUMNS.map((col) => ({
              key: col.key,
              header: col.header,
              align: col.key === "basic_salary" ? ("right" as const) : undefined,
              render:
                col.key === "basic_salary"
                  ? (r) => formatReportAmount(r.basic_salary)
                  : undefined,
            }))}
          />
          {data && data.total > 0 && (
            <TablePagination
              total={data.total}
              limit={data.limit}
              offset={data.offset}
              onPageChange={setPage}
              disabled={isFetching || exporting}
            />
          )}
        </div>
      )}
    </div>
  );
}
