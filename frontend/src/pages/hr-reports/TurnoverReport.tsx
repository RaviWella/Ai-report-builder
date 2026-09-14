import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import MetricCard from "../../components/MetricCard";
import PeriodFilter from "../../components/PeriodFilter";
import ReportCrossLink from "../../components/ReportCrossLink";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportMetricsSkeleton } from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import { reportNoPeriodEmpty } from "./hrReportEmptyStates";

export default function TurnoverReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["headcount", period],
    queryFn: () => hrApi.getHeadcount({ period_label: period }),
    enabled: !!period,
  });

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader
        title="Turnover & attrition"
        description="Separations and turnover rate for attrition review during month-end close."
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <ReportMetricsSkeleton count={2} />
      ) : isError ? (
        <ReportQueryError
          title="Could not load turnover data"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-2">
            <MetricCard label="Separations" value={data?.separations} unit="count" goodDirection="down" />
            <MetricCard label="Turnover rate" value={data?.turnover_rate} unit="percent" goodDirection="down" />
          </div>
          <ReportCrossLink to="/hr/headcount">View full headcount trend</ReportCrossLink>
        </>
      )}
    </div>
  );
}
