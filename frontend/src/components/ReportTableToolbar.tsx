import type { ReactNode } from "react";
import { Download, Loader2 } from "lucide-react";
import clsx from "clsx";

export interface ReportTableToolbarProps {
  onExportCsv?: () => void | Promise<void>;
  exporting?: boolean;
  exportDisabled?: boolean;
  exportLabel?: string;
  children?: ReactNode;
}

export default function ReportTableToolbar({
  onExportCsv,
  exporting = false,
  exportDisabled = false,
  exportLabel = "Download CSV",
  children,
}: ReportTableToolbarProps) {
  const showExport = !!onExportCsv;

  if (!showExport && !children) return null;

  return (
    <div className="hrm-table-toolbar">
      {children ? <div className="hrm-table-toolbar__slot min-w-0 flex-1">{children}</div> : null}
      {showExport ? (
        <button
          type="button"
          onClick={() => void onExportCsv?.()}
          disabled={exportDisabled || exporting}
          className={clsx(
            "hrm-table-toolbar__export",
            (exportDisabled || exporting) && "hrm-table-toolbar__export--disabled",
          )}
          aria-busy={exporting}
        >
          {exporting ? (
            <>
              <Loader2 size={16} className="hrm-table-toolbar__spin" aria-hidden />
              Exporting…
            </>
          ) : (
            <>
              <Download size={16} aria-hidden />
              {exportLabel}
            </>
          )}
        </button>
      ) : null}
    </div>
  );
}
