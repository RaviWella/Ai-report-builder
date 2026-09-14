import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportMetricsSkeleton } from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import { reportNoPeriodEmpty } from "./hrReportEmptyStates";

export default function AttendanceReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const { data: mart, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["attendance-monthly", period],
    queryFn: () => hrApi.getAttendanceMonthly(period),
    enabled: !!period,
  });

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader
        title="Attendance"
        description="Monthly attendance summary for the selected period."
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <ReportMetricsSkeleton count={3} />
      ) : isError ? (
        <ReportQueryError
          title="Could not load attendance"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <MetricCard label="Attendance rate" value={mart?.attendance_rate} unit="percent" goodDirection="up" />
          <MetricCard label="Late days" value={mart?.late_arrivals} unit="count" goodDirection="down" />
          <MetricCard label="Overtime hours" value={mart?.total_overtime_hours} unit="hours" />
        </div>
      )}
    </div>
  );
}
