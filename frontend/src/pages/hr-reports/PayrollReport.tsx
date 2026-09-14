import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import DataTable from "../../components/DataTable";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import ReportSection from "../../components/ReportSection";
import ReportTableToolbar from "../../components/ReportTableToolbar";
import { useToast } from "../../components/ui/Toast";
import {
  exportHrRowsToCsv,
  fetchAllHrPages,
  sanitizeCsvFilenamePart,
} from "../../lib/exportHrTableCsv";
import { formatReportAmount } from "../../lib/reportAmountFormat";
import {
  ReportMetricsSkeleton,
  ReportTableSkeleton,
} from "../../components/ReportLoadingSkeleton";
import TablePagination from "../../components/TablePagination";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import type {
  PayrollComplianceRow,
  PayrollComponentRow,
  PayrollRegisterRow,
} from "../../services/api";
import {
  payrollComplianceEmpty,
  payrollComponentsEmpty,
  payrollRegisterEmpty,
  reportNoPeriodEmpty,
} from "./hrReportEmptyStates";
import { PAYROLL_REGISTER_COLUMNS } from "./payrollRegisterColumns";

const PAGE_SIZE = 50;
const EXPORT_PAGE_SIZE = 500;

function complianceLabel(domain: string) {
  const labels: Record<string, string> = {
    epf_employee: "EPF (employee)",
    epf_employer: "EPF (employer)",
    etf: "ETF",
  };
  return labels[domain] ?? domain;
}

export default function PayrollReport() {
  const toast = useToast();
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const [page, setPage] = useState(0);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setPage(0);
  }, [period]);

  const offset = page * PAGE_SIZE;

  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    error: summaryErr,
    refetch: refetchSummary,
    isFetching: summaryFetching,
  } = useQuery({
    queryKey: ["payroll-summary", period],
    queryFn: () => hrApi.getPayrollSummary(period),
    enabled: !!period,
  });

  const {
    data: register,
    isLoading: registerLoading,
    isFetching,
    isError: registerError,
    error: registerErr,
    refetch: refetchRegister,
    isRefetching: registerRefetching,
  } = useQuery({
    queryKey: ["payroll-register", period, page],
    queryFn: () =>
      hrApi.getPayrollRegister({
        limit: PAGE_SIZE,
        offset,
        period_label: period,
      }),
    enabled: !!period,
    placeholderData: (prev) => prev,
  });

  const { data: compliance, isLoading: complianceLoading } = useQuery({
    queryKey: ["payroll-compliance", period],
    queryFn: () => hrApi.getPayrollCompliance(period),
    enabled: !!period,
  });

  const { data: components, isLoading: componentsLoading } = useQuery({
    queryKey: ["payroll-components", period],
    queryFn: () => hrApi.getPayrollComponents({ period_label: period, limit: 20 }),
    enabled: !!period,
  });

  const loading =
    periodLoading ||
    summaryLoading ||
    registerLoading ||
    complianceLoading ||
    componentsLoading;

  const loadFailed = summaryError || registerError;
  const loadMessage = summaryError
    ? getErrorMessage(summaryErr)
    : getErrorMessage(registerErr);
  const retrying = summaryFetching || registerRefetching;

  function handleRetry() {
    if (summaryError) void refetchSummary();
    if (registerError) void refetchRegister();
  }

  const overviewTitle = period ? `Overview (${period})` : "Overview";

  const handleExportRegisterCsv = useCallback(async () => {
    if (!period || !register?.total) return;
    setExporting(true);
    try {
      const rows = await fetchAllHrPages({
        total: register.total,
        pageSize: EXPORT_PAGE_SIZE,
        fetchPage: (off, limit) =>
          hrApi.getPayrollRegister({ period_label: period, offset: off, limit }),
      });
      exportHrRowsToCsv(
        PAYROLL_REGISTER_COLUMNS,
        rows,
        `payroll-register-${sanitizeCsvFilenamePart(period)}.csv`,
      );
      toast.success(
        "CSV downloaded",
        `${rows.length.toLocaleString()} payroll row${rows.length === 1 ? "" : "s"} exported.`,
      );
    } catch (e) {
      toast.error("Export failed", getErrorMessage(e));
    } finally {
      setExporting(false);
    }
  }, [period, register?.total, toast]);

  return (
    <div className="hrm-report-page hrm-report-page--spaced-lg">
      <ReportPageHeader
        title="Payroll"
        description={`Processed payroll from engine snapshots${
          summary?.payroll_employee_count != null
            ? ` · ${summary.payroll_employee_count.toLocaleString()} employees`
            : ""
        }`}
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>

      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : loading ? (
        <div className="space-y-8">
          <ReportMetricsSkeleton count={8} />
          <ReportTableSkeleton rows={8} />
          <ReportTableSkeleton rows={5} />
        </div>
      ) : loadFailed ? (
        <ReportQueryError
          title="Could not load payroll data"
          message={loadMessage}
          onRetry={handleRetry}
          retrying={retrying}
        />
      ) : (
        <>
          <ReportSection title={overviewTitle}>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <MetricCard label="Net payroll" value={summary?.total_payroll_cost} unit="currency" />
              <MetricCard label="Gross pay" value={summary?.total_gross} unit="currency" />
              <MetricCard label="Avg net salary" value={summary?.average_salary} unit="currency" />
              <MetricCard label="Employees paid" value={summary?.payroll_employee_count} unit="count" />
              <MetricCard label="Total tax" value={summary?.total_tax} unit="currency" goodDirection="down" />
              <MetricCard label="Statutory (EPF + ETF)" value={summary?.total_statutory} unit="currency" />
              <MetricCard label="Additions" value={summary?.total_additions} unit="currency" />
              <MetricCard
                label="Deductions"
                value={
                  summary?.total_deductions ??
                  (summary?.total_gross != null && summary?.total_payroll_cost != null
                    ? summary.total_gross - summary.total_payroll_cost
                    : undefined)
                }
                unit="currency"
                goodDirection="down"
              />
            </div>
          </ReportSection>

          <ReportSection title="Statutory compliance">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {(compliance?.items ?? []).length === 0 ? (
                <div className="col-span-full">{payrollComplianceEmpty(period)}</div>
              ) : (
                compliance?.items.map((row: PayrollComplianceRow) => (
                  <MetricCard
                    key={row.compliance_domain}
                    label={complianceLabel(row.compliance_domain)}
                    value={row.total_amount}
                    unit="currency"
                  />
                ))
              )}
            </div>
          </ReportSection>

          <ReportSection title="Payroll register">
            <div className="space-y-3">
              <ReportTableToolbar
                onExportCsv={handleExportRegisterCsv}
                exporting={exporting}
                exportDisabled={!register?.total}
                exportLabel="Download register CSV"
              />
              <DataTable<PayrollRegisterRow>
                rows={register?.items ?? []}
                emptyContent={payrollRegisterEmpty(period)}
                columns={[
                  { key: "emp_no", header: "Emp #" },
                  { key: "emp_fullname", header: "Name" },
                  { key: "payroll_group_name", header: "Pay group" },
                  { key: "designation", header: "Designation" },
                  {
                    key: "basic_salary",
                    header: "Basic",
                    align: "right",
                    render: (r) => formatReportAmount(r.basic_salary),
                  },
                  {
                    key: "gross_salary",
                    header: "Gross",
                    align: "right",
                    render: (r) => formatReportAmount(r.gross_salary),
                  },
                  {
                    key: "tax_amount",
                    header: "Tax",
                    align: "right",
                    render: (r) => formatReportAmount(r.tax_amount),
                  },
                  {
                    key: "net_salary",
                    header: "Net",
                    align: "right",
                    render: (r) => formatReportAmount(r.net_salary),
                  },
                ]}
              />
              {register && register.total > 0 && (
                <TablePagination
                  total={register.total}
                  limit={register.limit}
                  offset={register.offset}
                  onPageChange={setPage}
                  disabled={isFetching || exporting}
                />
              )}
            </div>
          </ReportSection>

          <ReportSection title="Pay components">
            <DataTable<PayrollComponentRow>
              rows={components?.items ?? []}
              emptyContent={payrollComponentsEmpty(period)}
              columns={[
                { key: "component_name", header: "Component" },
                {
                  key: "add_ded_type",
                  header: "Type",
                  render: (r) => (r.add_ded_type === "addition" ? "Addition" : "Deduction"),
                },
                { key: "line_count", header: "Lines", align: "right" },
                { key: "total_amount", header: "Amount", align: "right", render: (r) => formatReportAmount(r.total_amount) },
              ]}
            />
          </ReportSection>
        </>
      )}
    </div>
  );
}
