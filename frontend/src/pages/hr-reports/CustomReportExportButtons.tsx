import { Download, FileText, Loader2 } from "lucide-react";

type ExportFormat = "xlsx" | "pdf";

interface CustomReportExportButtonsProps {
  downloading: ExportFormat | null;
  disabled?: boolean;
  onDownload: (format: ExportFormat) => void;
}

export default function CustomReportExportButtons({
  downloading,
  disabled = false,
  onDownload,
}: CustomReportExportButtonsProps) {
  const busy = disabled || downloading !== null;
  const excelBusy = downloading === "xlsx";
  const pdfBusy = downloading === "pdf";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => onDownload("xlsx")}
        disabled={busy}
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
        onClick={() => onDownload("pdf")}
        disabled={busy}
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
  );
}
