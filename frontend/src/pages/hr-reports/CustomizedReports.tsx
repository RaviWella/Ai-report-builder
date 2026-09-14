import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Download, Eye, FileText, Loader2 } from "lucide-react";
import ReportEmptyState from "../../components/ReportEmptyState";
import ReportPageHeader from "../../components/ReportPageHeader";
import ReportQueryError from "../../components/ReportQueryError";
import { ReportListSkeleton } from "../../components/ReportLoadingSkeleton";
import { groupCustomReportsForDisplay } from "../../lib/customReportModules";
import {
  CUSTOM_REPORTS_QUERY_KEY,
  CUSTOM_REPORTS_STALE_MS,
} from "../../lib/customReportsQuery";
import { getErrorMessage, hrApi, type CustomReportView } from "../../services/api";

type ExportFormat = "xlsx" | "pdf";

function ReportRow({
  view,
  downloading,
  onDownload,
}: {
  view: CustomReportView;
  downloading: { viewName: string; format: ExportFormat } | null;
  onDownload: (view: CustomReportView, format: ExportFormat) => void;
}) {
  const rowBusy = downloading?.viewName === view.view_name;
  const excelBusy = rowBusy && downloading?.format === "xlsx";
  const pdfBusy = rowBusy && downloading?.format === "pdf";

  return (
    <li>
      <div className="flex w-full flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-slate-900 truncate">{view.label}</p>
        </div>
        <div className="inline-flex shrink-0 flex-wrap items-center gap-2">
          <Link
            to={`/hr/custom-reports/${encodeURIComponent(view.view_name)}`}
            className="hrm-report-action hrm-report-action--secondary"
          >
            <Eye size={14} aria-hidden />
            Preview report
          </Link>
          <button
            type="button"
            onClick={() => onDownload(view, "xlsx")}
            disabled={rowBusy}
            className="hrm-report-action hrm-report-action--primary"
            aria-busy={excelBusy}
          >
            {excelBusy ? (
              <>
                <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                Exporting…
              </>
            ) : (
              <>
                <Download size={14} aria-hidden />
                Download Excel
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => onDownload(view, "pdf")}
            disabled={rowBusy}
            className="hrm-report-action hrm-report-action--muted"
            aria-busy={pdfBusy}
          >
            {pdfBusy ? (
              <>
                <Loader2 size={14} className="hrm-table-toolbar__spin" aria-hidden />
                Exporting…
              </>
            ) : (
              <>
                <FileText size={14} aria-hidden />
                Download PDF
              </>
            )}
          </button>
        </div>
      </div>
    </li>
  );
}

export default function CustomizedReports() {
  const [downloading, setDownloading] = useState<{ viewName: string; format: ExportFormat } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, isError, error: loadError, refetch, isFetching } = useQuery({
    queryKey: CUSTOM_REPORTS_QUERY_KEY,
    queryFn: () => hrApi.listCustomReports(),
    staleTime: CUSTOM_REPORTS_STALE_MS,
  });

  const views = data?.views ?? [];
  const sections = groupCustomReportsForDisplay(views);
  const loadFailed = isError && !isLoading;

  async function handleDownload(view: CustomReportView, format: ExportFormat) {
    setError(null);
    setDownloading({ viewName: view.view_name, format });
    try {
      await hrApi.downloadCustomReport(view.view_name, format, undefined, view.label);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="hrm-report-page hrm-report-page--spaced max-w-5xl">
      <ReportPageHeader
        title="Report Studio"
        description="Registered reports for this tenant, grouped by area. Preview in the browser or download Excel or PDF."
      />

      {loadFailed && (
        <ReportQueryError
          title="Could not load reports"
          message={getErrorMessage(loadError)}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {error && (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex items-start justify-between gap-3"
          role="alert"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="shrink-0 text-red-700 underline underline-offset-2 hover:text-red-900"
          >
            Dismiss
          </button>
        </div>
      )}

      {isLoading ? (
        <ReportListSkeleton rows={4} />
      ) : !loadFailed && views.length === 0 ? (
        <ReportEmptyState
          title="No reports available yet"
          hint="Standard payroll reports load after ETL. Tenant reports must be saved and published in Report Studio Config before they appear here."
          action={{ label: "Open Report Studio Config", to: "/settings/custom-reports" }}
        />
      ) : !loadFailed ? (
        <div className="space-y-8">
          {sections.map((section) => (
            <section key={section.id} aria-labelledby={`custom-reports-${section.id}`}>
              <h2
                id={`custom-reports-${section.id}`}
                className="text-sm font-semibold text-slate-700 mb-3 text-balance"
              >
                {section.title}
              </h2>
              <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white shadow-sm">
                {section.views.map((view) => (
                  <ReportRow
                    key={view.view_name}
                    view={view}
                    downloading={downloading}
                    onDownload={handleDownload}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      ) : null}
    </div>
  );
}
