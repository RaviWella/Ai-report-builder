/**
 * HR Dashboard — month-end snapshot with headline KPIs and links to full reports.
 */
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import ReportSection from "../../components/ReportSection";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import { HR_CURRENCY } from "../../env";
import { reportNoPeriodEmpty } from "./hrReportEmptyStates";

type CompactMetric = {
  label: string;
  value: number | null | undefined;
  unit?: "count" | "percent" | "currency" | "hours";
};

function formatCompact(
  value: number | null | undefined,
  unit: CompactMetric["unit"] = "count",
): string {
  if (value === null || value === undefined) return "—";
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "currency") {
    return new Intl.NumberFormat("en-LK", {
      style: "currency",
      currency: HR_CURRENCY,
      maximumFractionDigits: 0,
    }).format(value);
  }
  if (unit === "hours") return `${value.toFixed(1)} h`;
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function ReportPanel({
  title,
  to,
  metrics,
}: {
  title: string;
  to: string;
  metrics: CompactMetric[];
}) {
  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-white p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="hrm-report-panel-title">{title}</h2>
        <Link
          to={to}
          className="inline-flex min-h-[2.75rem] items-center gap-1 text-sm font-medium text-teal-800 hover:text-teal-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600"
        >
          View report
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <dt className="hrm-metric-compact__label">{metric.label}</dt>
            <dd className="hrm-metric-compact__value">
              {formatCompact(metric.value, metric.unit)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-10" aria-busy="true" aria-label="Loading dashboard">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-[7.5rem] hrm-skeleton rounded-xl border border-teal-100 bg-teal-50/30"
          />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-36 hrm-skeleton rounded-xl border border-slate-200 bg-white"
          />
        ))}
      </div>
    </div>
  );
}

export default function HRDashboard() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();

  const {
    data: employment,
    isLoading: empLoading,
    isError: empError,
    error: empErr,
    refetch: refetchEmp,
    isFetching: empFetching,
  } = useQuery({
    queryKey: ["employment-summary", period],
    queryFn: () => hrApi.getEmploymentSummary(period),
    enabled: !!period,
  });

  const {
    data: payroll,
    isLoading: prLoading,
    isError: prError,
    error: prErr,
    refetch: refetchPr,
    isFetching: prFetching,
  } = useQuery({
    queryKey: ["payroll", period],
    queryFn: () => hrApi.getPayroll({ period_label: period }),
    enabled: !!period,
  });

  const {
    data: attendanceMart,
    isLoading: attMartLoading,
    isError: attError,
    error: attErr,
    refetch: refetchAtt,
    isFetching: attFetching,
  } = useQuery({
    queryKey: ["attendance-monthly", period],
    queryFn: () => hrApi.getAttendanceMonthly(period),
    enabled: !!period,
  });

  const {
    data: leave,
    isLoading: lvLoading,
    isError: lvError,
    error: lvErr,
    refetch: refetchLv,
    isFetching: lvFetching,
  } = useQuery({
    queryKey: ["leave", period],
    queryFn: () => hrApi.getLeave({ period_label: period }),
    enabled: !!period,
  });

  const {
    data: performance,
    isLoading: perfLoading,
    isError: perfError,
    error: perfErr,
    refetch: refetchPerf,
    isFetching: perfFetching,
  } = useQuery({
    queryKey: ["performance", period],
    queryFn: () => hrApi.getPerformance({ period_label: period }),
    enabled: !!period,
  });

  const {
    data: headcount,
    isLoading: hcLoading,
    isError: hcError,
    error: hcErr,
    refetch: refetchHc,
    isFetching: hcFetching,
  } = useQuery({
    queryKey: ["headcount", period],
    queryFn: () => hrApi.getHeadcount({ period_label: period }),
    enabled: !!period,
  });

  const isLoading =
    periodLoading ||
    empLoading ||
    prLoading ||
    attMartLoading ||
    lvLoading ||
    perfLoading ||
    hcLoading;

  const loadFailed = empError || prError || attError || lvError || perfError || hcError;
  const loadMessage = empError
    ? getErrorMessage(empErr)
    : prError
      ? getErrorMessage(prErr)
      : attError
        ? getErrorMessage(attErr)
        : lvError
          ? getErrorMessage(lvErr)
          : perfError
            ? getErrorMessage(perfErr)
            : getErrorMessage(hcErr);
  const retrying =
    empFetching || prFetching || attFetching || lvFetching || perfFetching || hcFetching;

  function handleRetry() {
    if (empError) void refetchEmp();
    if (prError) void refetchPr();
    if (attError) void refetchAtt();
    if (lvError) void refetchLv();
    if (perfError) void refetchPerf();
    if (hcError) void refetchHc();
  }

  const periodLabel = period ? ` for ${period}` : "";

  return (
    <div className="hrm-report-page mx-auto max-w-7xl pb-10 hrm-report-page--spaced-lg">
      <ReportPageHeader
        title="HR dashboard"
        description={`Month-end snapshot${periodLabel}. Open a report for full tables and history.`}
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>

      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : isLoading ? (
        <DashboardSkeleton />
      ) : loadFailed ? (
        <ReportQueryError
          title="Could not load dashboard data"
          message={loadMessage}
          onRetry={handleRetry}
          retrying={retrying}
        />
      ) : (
        <div className="space-y-10">
          <section aria-labelledby="dashboard-headline">
            <h2 id="dashboard-headline" className="sr-only">
              Headline metrics
            </h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <MetricCard
                variant="lead"
                label="Active headcount (EOM)"
                value={employment?.active_headcount ?? headcount?.total_headcount}
                unit="count"
                goodDirection="up"
              />
              <MetricCard
                variant="lead"
                label="Net payroll processed"
                value={payroll?.total_payroll_cost}
                unit="currency"
              />
              <MetricCard
                variant="lead"
                label="Attendance rate"
                value={attendanceMart?.attendance_rate}
                unit="percent"
                goodDirection="up"
              />
              <MetricCard
                variant="lead"
                label="Turnover rate"
                value={employment?.turnover_rate ?? headcount?.turnover_rate}
                unit="percent"
                goodDirection="down"
              />
            </div>
          </section>

          <ReportSection title="Reports">
            <div className="grid gap-6 lg:grid-cols-2">
              <ReportPanel
                title="Headcount & movement"
                to="/hr/headcount"
                metrics={[
                  {
                    label: "New hires",
                    value: employment?.new_hires ?? headcount?.new_hires,
                    unit: "count",
                  },
                  {
                    label: "Separations",
                    value: employment?.separations ?? headcount?.separations,
                    unit: "count",
                  },
                  {
                    label: "MoM change",
                    value: employment?.mom_active_change,
                    unit: "count",
                  },
                ]}
              />
              <ReportPanel
                title="Compensation & payroll"
                to="/hr/payroll"
                metrics={[
                  {
                    label: "Gross payroll",
                    value: payroll?.total_gross,
                    unit: "currency",
                  },
                  {
                    label: "Avg net salary",
                    value: payroll?.average_salary,
                    unit: "currency",
                  },
                  {
                    label: "Payroll tax",
                    value: payroll?.total_tax,
                    unit: "currency",
                  },
                ]}
              />
              <ReportPanel
                title="Attendance & leave"
                to="/hr/attendance"
                metrics={[
                  {
                    label: "Late days",
                    value: attendanceMart?.late_arrivals,
                    unit: "count",
                  },
                  {
                    label: "Overtime hours",
                    value: attendanceMart?.total_overtime_hours,
                    unit: "hours",
                  },
                  {
                    label: "Leave utilization",
                    value: leave?.leave_utilization_rate,
                    unit: "percent",
                  },
                ]}
              />
              <ReportPanel
                title="Performance"
                to="/hr/performance"
                metrics={[
                  {
                    label: "Avg performance score",
                    value: performance?.average_performance_score,
                    unit: "count",
                  },
                  {
                    label: "High performers",
                    value: performance?.high_performers,
                    unit: "count",
                  },
                  {
                    label: "Avg basic salary",
                    value: employment?.average_basic_salary,
                    unit: "currency",
                  },
                ]}
              />
            </div>
          </ReportSection>
        </div>
      )}
    </div>
  );
}
