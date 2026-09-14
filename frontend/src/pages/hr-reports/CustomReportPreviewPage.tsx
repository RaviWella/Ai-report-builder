import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import ReportEmptyState from "../../components/ReportEmptyState";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportTableSkeleton } from "../../components/ReportLoadingSkeleton";
import { getErrorMessage, hrApi, PAYSLIP_REPORT_VIEW } from "../../services/api";
import {
  CUSTOM_REPORTS_QUERY_KEY,
  CUSTOM_REPORTS_STALE_MS,
} from "../../lib/customReportsQuery";
import GenericCustomReportPreview from "./GenericCustomReportPreview";
import PayslipPreviewPanel from "./PayslipPreviewPanel";

export default function CustomReportPreviewPage() {
  const { viewName = "" } = useParams();
  const decodedViewName = decodeURIComponent(viewName);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: CUSTOM_REPORTS_QUERY_KEY,
    queryFn: () => hrApi.listCustomReports(),
    staleTime: CUSTOM_REPORTS_STALE_MS,
  });

  const view = data?.views.find((item) => item.view_name === decodedViewName);

  if (isLoading) {
    return (
      <div className="hrm-report-page hrm-report-page--spaced">
        <Link to="/hr/custom-reports" className="hrm-report-back">
          <ArrowLeft size={16} aria-hidden />
          Back to Report Studio
        </Link>
        <div className="hrm-skeleton mt-4 h-8 w-64 max-w-full rounded" aria-hidden />
        <div className="hrm-skeleton mt-2 h-4 w-96 max-w-full rounded" aria-hidden />
        <div className="mt-6">
          <ReportTableSkeleton rows={8} />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="hrm-report-page hrm-report-page--spaced max-w-3xl">
        <Link to="/hr/custom-reports" className="hrm-report-back">
          <ArrowLeft size={16} aria-hidden />
          Back to Report Studio
        </Link>
        <ReportQueryError
          title="Could not load report"
          message={getErrorMessage(error)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      </div>
    );
  }

  if (!view) {
    return (
      <div className="hrm-report-page hrm-report-page--spaced max-w-3xl">
        <Link to="/hr/custom-reports" className="hrm-report-back">
          <ArrowLeft size={16} aria-hidden />
          Back to Report Studio
        </Link>
        <ReportEmptyState
          title="Report not found"
          hint={`No report named ${decodedViewName} is registered for this tenant. Run ETL, publish in Report Studio Config, or pick another report in Report Studio.`}
          action={{ label: "View Report Studio", to: "/hr/custom-reports" }}
        />
      </div>
    );
  }

  if (view.view_name === PAYSLIP_REPORT_VIEW) {
    return <PayslipPreviewPanel view={view} />;
  }

  return <GenericCustomReportPreview view={view} />;
}
