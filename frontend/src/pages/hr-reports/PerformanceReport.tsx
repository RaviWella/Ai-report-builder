import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportMetricsSkeleton } from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import { reportNoPeriodEmpty } from "./hrReportEmptyStates";

export default function PerformanceReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["performance", period],
    queryFn: () => hrApi.getPerformance({ period_label: period }),
    enabled: !!period,
  });

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader
        title="Performance"
        description="Performance scores and high-performer counts for the selected period."
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <ReportMetricsSkeleton count={2} />
      ) : isError ? (
        <ReportQueryError
          title="Could not load performance data"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-2">
          <MetricCard
            label="Avg performance score"
            value={data?.average_performance_score}
            unit="count"
            goodDirection="up"
          />
          <MetricCard
            label="High performers"
            value={data?.high_performers}
            unit="count"
            goodDirection="up"
          />
        </div>
      )}
    </div>
  );
}
