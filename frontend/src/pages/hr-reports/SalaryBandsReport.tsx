import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import DataTable from "../../components/DataTable";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import {
  ReportMetricsSkeleton,
  ReportTableSkeleton,
} from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import type { SalaryBandRow } from "../../services/api";
import { reportNoPeriodEmpty, salaryBandsTableEmpty } from "./hrReportEmptyStates";

import { formatReportAmount } from "../../lib/reportAmountFormat";

export default function SalaryBandsReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const {
    data: summary,
    isError: summaryError,
    error: summaryErr,
    refetch: refetchSummary,
    isFetching: summaryFetching,
  } = useQuery({
    queryKey: ["employment-summary", period],
    queryFn: () => hrApi.getEmploymentSummary(period),
    enabled: !!period,
  });
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["salary-bands", period],
    queryFn: () => hrApi.getSalaryBands({ limit: 100, period_label: period }),
    enabled: !!period,
    staleTime: 0,
    refetchOnMount: "always",
  });
  const rows = data?.items ?? [];
  const loadFailed = summaryError || isError;
  const loadMessage = summaryError
    ? getErrorMessage(summaryErr)
    : getErrorMessage(error);
  const retrying = summaryFetching || isFetching;

  function handleRetry() {
    if (summaryError) void refetchSummary();
    if (isError) void refetch();
  }

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader
        title="Salary bands"
        description={`Compensation bands by legal entity, designation, and grade${
          period ? ` · ${period}` : ""
        }`}
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <>
          <ReportMetricsSkeleton count={3} />
          <ReportTableSkeleton />
        </>
      ) : loadFailed ? (
        <ReportQueryError
          title="Could not load salary bands"
          message={loadMessage}
          onRetry={handleRetry}
          retrying={retrying}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <MetricCard
              label="Bands"
              value={rows.length || summary?.salary_band_count}
              unit="count"
            />
            <MetricCard
              label="Avg basic salary"
              value={summary?.average_basic_salary}
              unit="currency"
            />
            <MetricCard
              label="Total basic cost"
              value={summary?.total_basic_salary_cost}
              unit="currency"
            />
          </div>
          <DataTable<SalaryBandRow>
            rows={rows}
            emptyContent={salaryBandsTableEmpty(period)}
            columns={[
              { key: "legal_entity_name", header: "Legal entity" },
              { key: "designation_name", header: "Designation" },
              { key: "grade_name", header: "Grade" },
              {
                key: "headcount",
                header: "HC",
                align: "right",
                render: (r) => (r.headcount != null ? r.headcount.toLocaleString() : "—"),
              },
              {
                key: "min_salary",
                header: "Min",
                align: "right",
                render: (r) => formatReportAmount(r.min_salary),
              },
              {
                key: "avg_salary",
                header: "Avg",
                align: "right",
                render: (r) => formatReportAmount(r.avg_salary),
              },
              {
                key: "max_salary",
                header: "Max",
                align: "right",
                render: (r) => formatReportAmount(r.max_salary),
              },
              {
                key: "payroll_cost",
                header: "Payroll",
                align: "right",
                render: (r) => formatReportAmount(r.payroll_cost),
              },
            ]}
          />
        </>
      )}
    </div>
  );
}
