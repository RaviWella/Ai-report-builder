import { Link } from "react-router-dom";

export interface ReportEmptyStateProps {
  title: string;
  hint: string;
  action?: { label: string; to: string };
}

export default function ReportEmptyState({ title, hint, action }: ReportEmptyStateProps) {
  return (
    <div className="hrm-report-empty" role="status">
      <p className="hrm-report-empty__title">{title}</p>
      <p className="hrm-report-empty__hint">{hint}</p>
      {action ? (
        <Link to={action.to} className="hrm-report-empty__action">
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}
