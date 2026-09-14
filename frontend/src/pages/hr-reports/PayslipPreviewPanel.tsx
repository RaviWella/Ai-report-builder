import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, FileText, Loader2 } from "lucide-react";
import DataTable from "../../components/DataTable";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportTableSkeleton } from "../../components/ReportLoadingSkeleton";
import CustomReportPreviewHeader from "./CustomReportPreviewHeader";
import { parsePeriodKey, periodKey, periodLabel } from "./customReportPeriod";
import {
  getErrorMessage,
  hrApi,
  type CustomReportView,
  type PayslipFilterEntry,
} from "../../services/api";
import { formatReportColumnLabel } from "./columnFilterUtils";
import { payslipLinesEmpty } from "./hrReportEmptyStates";
import { formatReportAmount } from "../../lib/reportAmountFormat";

function employeeLabel(entry: PayslipFilterEntry) {
  const name = entry.emp_full_name || entry.emp_name || entry.emp_no;
  return `${entry.emp_no} — ${name}`;
}

interface PayslipPreviewPanelProps {
  view: CustomReportView;
}

export default function PayslipPreviewPanel({ view }: PayslipPreviewPanelProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [selectedEmpNo, setSelectedEmpNo] = useState<string>("");
  const [downloading, setDownloading] = useState<{
    format: "xlsx" | "pdf";
    scope: "employee" | "period";
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    data: filters,
    isLoading: filtersLoading,
    isError: filtersError,
    error: filtersLoadError,
  } = useQuery({
    queryKey: ["payslip-filters", view.view_name],
    queryFn: () => hrApi.listPayslipFilters(view.view_name),
  });

  const periods = useMemo(() => {
    const seen = new Set<string>();
    const list: { key: string; year: number; month: number }[] = [];
    for (const entry of filters?.entries ?? []) {
      const key = periodKey(entry.proc_year, entry.proc_month);
      if (seen.has(key)) continue;
      seen.add(key);
      list.push({ key, year: entry.proc_year, month: entry.proc_month });
    }
    return list;
  }, [filters]);

  const employeesForPeriod = useMemo(() => {
    if (!selectedPeriod) return [];
    return (filters?.entries ?? []).filter(
      (entry) => periodKey(entry.proc_year, entry.proc_month) === selectedPeriod,
    );
  }, [filters, selectedPeriod]);

  const selectedEmployee = employeesForPeriod.find((e) => e.emp_no === selectedEmpNo);
  const employeeIndex = employeesForPeriod.findIndex((e) => e.emp_no === selectedEmpNo);

  useEffect(() => {
    if (!periods.length) return;
    setSelectedPeriod((current) => current || periods[0].key);
  }, [periods]);

  useEffect(() => {
    if (!employeesForPeriod.length) {
      setSelectedEmpNo("");
      return;
    }
    setSelectedEmpNo((current) => {
      if (current && employeesForPeriod.some((e) => e.emp_no === current)) return current;
      return employeesForPeriod[0].emp_no;
    });
  }, [employeesForPeriod]);

  const periodParts = selectedPeriod ? parsePeriodKey(selectedPeriod) : null;

  const {
    data: payslip,
    isLoading: payslipLoading,
    isFetching,
    isError: payslipError,
    error: payslipLoadError,
  } = useQuery({
    queryKey: ["payslip-preview", view.view_name, selectedEmpNo, selectedPeriod],
    queryFn: () =>
      hrApi.previewPayslip(view.view_name, {
        emp_no: selectedEmpNo,
        proc_year: periodParts!.proc_year,
        proc_month: periodParts!.proc_month,
      }),
    enabled: !!selectedEmpNo && !!selectedPeriod,
    placeholderData: (prev) => prev,
  });

  const columns =
    payslip?.columns.map((column) => ({
      key: column,
      header: formatReportColumnLabel(column),
      align: column === "amount" ? ("right" as const) : ("left" as const),
      render:
        column === "amount"
          ? (row: Record<string, unknown>) => formatReportAmount(row.amount)
          : undefined,
    })) ?? [];

  function goToEmployee(delta: number) {
    if (!employeesForPeriod.length) return;
    const next =
      (employeeIndex + delta + employeesForPeriod.length) % employeesForPeriod.length;
    setSelectedEmpNo(employeesForPeriod[next].emp_no);
  }

  async function handleDownload(format: "xlsx" | "pdf", scope: "employee" | "period") {
    if (!periodParts) return;
    setError(null);
    setDownloading({ format, scope });
    try {
      await hrApi.downloadCustomReport(
        view.view_name,
        format,
        {
          ...periodParts,
          ...(scope === "employee" ? { emp_no: selectedEmpNo } : {}),
        },
        view.label,
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDownloading(null);
    }
  }

  const exportBusy = downloading !== null;

  return (
    <div className="hrm-report-page hrm-report-page--spaced space-y-6">
      <CustomReportPreviewHeader
        title={view.label}
        subtitle="Select a payroll period and employee to preview payslip lines."
      />

      {error && <ReportQueryError title="Export failed" message={error} />}

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        {filtersLoading ? (
          <div className="grid gap-3 sm:grid-cols-2" aria-busy="true" aria-label="Loading filters">
            <div className="hrm-skeleton h-[4.25rem] rounded-lg" />
            <div className="hrm-skeleton h-[4.25rem] rounded-lg" />
          </div>
        ) : filtersError ? (
          <ReportQueryError
            title="Could not load payslip filters"
            message={getErrorMessage(filtersLoadError)}
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Payroll period</span>
              <select
                value={selectedPeriod}
                onChange={(e) => setSelectedPeriod(e.target.value)}
                disabled={exportBusy}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
              >
                {periods.map((period) => (
                  <option key={period.key} value={period.key}>
                    {periodLabel(period.year, period.month)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Employee</span>
              <select
                value={selectedEmpNo}
                onChange={(e) => setSelectedEmpNo(e.target.value)}
                disabled={exportBusy}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
              >
                {employeesForPeriod.map((entry) => (
                  <option key={entry.emp_no} value={entry.emp_no}>
                    {employeeLabel(entry)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {selectedEmployee && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3 text-sm">
            <div>
              <p className="font-medium text-slate-900">
                {selectedEmployee.emp_full_name ||
                  selectedEmployee.emp_name ||
                  selectedEmployee.emp_no}
              </p>
              <p className="text-slate-600">
                {selectedEmployee.emp_no}
                {selectedEmployee.designation_name
                  ? ` · ${selectedEmployee.designation_name}`
                  : ""}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => goToEmployee(-1)}
                disabled={employeesForPeriod.length <= 1 || isFetching || exportBusy}
                className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-white disabled:opacity-40"
              >
                <ChevronLeft size={14} />
                Previous
              </button>
              <span className="text-xs text-slate-500 tabular-nums">
                {employeeIndex + 1} of {employeesForPeriod.length}
              </span>
              <button
                type="button"
                onClick={() => goToEmployee(1)}
                disabled={employeesForPeriod.length <= 1 || isFetching || exportBusy}
                className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-white disabled:opacity-40"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

        {selectedPeriod && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleDownload("xlsx", "employee")}
              disabled={!selectedEmpNo || exportBusy}
              className="hrm-report-action hrm-report-action--primary"
              aria-busy={downloading?.format === "xlsx" && downloading.scope === "employee"}
            >
              {downloading?.format === "xlsx" && downloading.scope === "employee" ? (
                <>
                  <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                  Exporting…
                </>
              ) : (
                <>
                  <Download size={14} aria-hidden />
                  Download Excel (employee)
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => handleDownload("pdf", "employee")}
              disabled={!selectedEmpNo || exportBusy}
              className="hrm-report-action hrm-report-action--muted"
              aria-busy={downloading?.format === "pdf" && downloading.scope === "employee"}
            >
              {downloading?.format === "pdf" && downloading.scope === "employee" ? (
                <>
                  <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                  Exporting…
                </>
              ) : (
                <>
                  <FileText size={14} aria-hidden />
                  Download PDF (employee)
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => handleDownload("xlsx", "period")}
              disabled={exportBusy}
              className="hrm-report-action hrm-report-action--secondary"
              aria-busy={downloading?.format === "xlsx" && downloading.scope === "period"}
            >
              {downloading?.format === "xlsx" && downloading.scope === "period" ? (
                <>
                  <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                  Exporting…
                </>
              ) : (
                <>
                  <Download size={14} aria-hidden />
                  Download Excel (period)
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => handleDownload("pdf", "period")}
              disabled={exportBusy}
              className="hrm-report-action hrm-report-action--secondary"
              aria-busy={downloading?.format === "pdf" && downloading.scope === "period"}
            >
              {downloading?.format === "pdf" && downloading.scope === "period" ? (
                <>
                  <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                  Exporting…
                </>
              ) : (
                <>
                  <FileText size={14} aria-hidden />
                  Download PDF (period)
                </>
              )}
            </button>
          </div>
        )}
      </section>

      <section>
        <h2 className="hrm-report-section-title mb-3">
          Payslip lines
        </h2>
        {payslipLoading ? (
          <ReportTableSkeleton rows={6} />
        ) : payslipError ? (
          <ReportQueryError
            title="Could not load payslip lines"
            message={getErrorMessage(payslipLoadError)}
          />
        ) : (
          <DataTable
            columns={columns}
            rows={payslip?.rows ?? []}
            stickyHeader
            emptyContent={payslipLinesEmpty()}
          />
        )}
      </section>
    </div>
  );
}
