import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import DataTable from "../../components/DataTable";
import PeriodFilter from "../../components/PeriodFilter";
import ReportCrossLink from "../../components/ReportCrossLink";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import ReportSection from "../../components/ReportSection";
import {
  ReportMetricsSkeleton,
  ReportTableSkeleton,
} from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import type { HeadcountMonthlyRow } from "../../services/api";
import { HR_CURRENCY } from "../../env";
import { formatReportAmount } from "../../lib/reportAmountFormat";
import { headcountMonthlyEmpty, reportNoPeriodEmpty } from "./hrReportEmptyStates";

export default function HeadcountReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const {
    data: summary,
    isLoading: sumLoading,
    isError: sumError,
    error: sumErr,
    refetch: refetchSummary,
    isFetching: sumFetching,
  } = useQuery({
    queryKey: ["employment-summary", period],
    queryFn: () => hrApi.getEmploymentSummary(period),
    enabled: !!period,
  });
  const {
    data: monthly,
    isLoading: monLoading,
    isError: monError,
    error: monErr,
    refetch: refetchMonthly,
    isFetching: monFetching,
  } = useQuery({
    queryKey: ["headcount-monthly", period],
    queryFn: () => hrApi.getHeadcountMonthly({ limit: 24 }),
    enabled: !!period,
  });

  const isLoading = periodLoading || sumLoading || monLoading;
  const loadFailed = sumError || monError;
  const loadMessage = sumError ? getErrorMessage(sumErr) : getErrorMessage(monErr);
  const retrying = sumFetching || monFetching;
  const rows = (monthly?.items ?? []).slice().reverse();

  function handleRetry() {
    if (sumError) void refetchSummary();
    if (monError) void refetchMonthly();
  }

  return (
    <div className="hrm-report-page hrm-report-page--spaced-lg">
      <ReportPageHeader
        title="Headcount & movement"
        description="Month-end active headcount, movement, and salary cost for the selected period. Table shows all available months."
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>

      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : isLoading ? (
        <>
          <ReportMetricsSkeleton count={5} />
          <ReportTableSkeleton />
        </>
      ) : loadFailed ? (
        <ReportQueryError
          title="Could not load headcount data"
          message={loadMessage}
          onRetry={handleRetry}
          retrying={retrying}
        />
      ) : (
        <>
          <ReportSection title={period ? `Overview (${period})` : "Overview"}>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
              <MetricCard
                label="Active (EOM)"
                value={summary?.active_headcount}
                unit="count"
                goodDirection="up"
              />
              <MetricCard label="MoM change" value={summary?.mom_active_change} unit="count" />
              <MetricCard
                label="New hires"
                value={summary?.new_hires}
                unit="count"
                goodDirection="up"
              />
              <MetricCard
                label="Separations"
                value={summary?.separations}
                unit="count"
                goodDirection="down"
              />
              <MetricCard
                label="Turnover rate"
                value={summary?.turnover_rate}
                unit="percent"
                goodDirection="down"
              />
            </div>
            <ReportCrossLink to="/hr/turnover">Review attrition details</ReportCrossLink>
          </ReportSection>

          <ReportSection title="Monthly trend">
            <DataTable<HeadcountMonthlyRow>
              rows={rows}
              emptyContent={headcountMonthlyEmpty()}
              columns={[
                { key: "period_label", header: "Month" },
                { key: "active_headcount", header: "Active EOM", align: "right" },
                { key: "net_active_headcount_change_mom", header: "MoM", align: "right" },
                {
                  key: "monthly_salary_cost_active",
                  header: HR_CURRENCY,
                  align: "right",
                  render: (r) => formatReportAmount(r.monthly_salary_cost_active),
                },
              ]}
            />
          </ReportSection>
        </>
      )}
    </div>
  );
}
