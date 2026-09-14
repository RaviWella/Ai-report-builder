import { AlertCircle } from "lucide-react";

interface ReportQueryErrorProps {
  title: string;
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
}

export default function ReportQueryError({
  title,
  message,
  onRetry,
  retrying,
}: ReportQueryErrorProps) {
  return (
    <div className="hrm-report-query-error" role="alert">
      <AlertCircle className="hrm-report-query-error__icon" aria-hidden />
      <div className="hrm-report-query-error__body">
        <p className="hrm-report-query-error__title">{title}</p>
        <p className="hrm-report-query-error__message">{message}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className="hrm-report-query-error__retry"
          >
            {retrying ? "Retrying…" : "Try again"}
          </button>
        ) : null}
      </div>
    </div>
  );
}
