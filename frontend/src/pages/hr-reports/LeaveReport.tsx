import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportMetricsSkeleton } from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import { reportNoPeriodEmpty } from "./hrReportEmptyStates";

export default function LeaveReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["leave", period],
    queryFn: () => hrApi.getLeave({ period_label: period }),
    enabled: !!period,
  });

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader title="Leave" description="Leave usage and entitlement for the selected period.">
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <ReportMetricsSkeleton count={4} />
      ) : isError ? (
        <ReportQueryError
          title="Could not load leave data"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <MetricCard label="Days taken" value={data?.leave_days_taken} unit="days" />
          <MetricCard label="Days entitled" value={data?.leave_days_entitled} unit="days" />
          <MetricCard label="Leave utilization" value={data?.leave_utilization_rate} unit="percent" />
          <MetricCard label="Sick leave days" value={data?.sick_leave_days} unit="days" goodDirection="down" />
        </div>
      )}
    </div>
  );
}
