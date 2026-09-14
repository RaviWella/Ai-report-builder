import { useQuery } from "@tanstack/react-query";
import { hrApi, getErrorMessage } from "../../services/api";
import DataTable from "../../components/DataTable";
import PeriodFilter from "../../components/PeriodFilter";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportTableSkeleton } from "../../components/ReportLoadingSkeleton";
import { useReportPeriod } from "../../hooks/useReportPeriod";
import type { LifecycleCategoryRow } from "../../services/api";
import { lifecycleTableEmpty, reportNoPeriodEmpty } from "./hrReportEmptyStates";

export default function LifecycleReport() {
  const { period, setPeriod, isLoading: periodLoading } = useReportPeriod();
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["lifecycle", period],
    queryFn: () => hrApi.getLifecycleSummary(period),
    enabled: !!period,
  });

  return (
    <div className="hrm-report-page hrm-report-page--spaced">
      <ReportPageHeader
        title="Lifecycle events"
        description="Employee lifecycle events grouped by category for the selected period."
      >
        <PeriodFilter value={period} onChange={setPeriod} />
      </ReportPageHeader>
      {!period && !periodLoading ? (
        reportNoPeriodEmpty()
      ) : periodLoading || isLoading ? (
        <ReportTableSkeleton rows={5} />
      ) : isError ? (
        <ReportQueryError
          title="Could not load lifecycle events"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      ) : (
        <DataTable<LifecycleCategoryRow>
          rows={data?.items ?? []}
          emptyContent={lifecycleTableEmpty(period)}
          columns={[
            { key: "event_category", header: "Category" },
            { key: "event_count", header: "Events", align: "right" },
          ]}
        />
      )}
    </div>
  );
}
