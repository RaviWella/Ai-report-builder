import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

interface CustomReportPreviewHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export default function CustomReportPreviewHeader({
  title,
  subtitle,
  actions,
}: CustomReportPreviewHeaderProps) {
  return (
    <header className="hrm-report-header">
      <div className="min-w-0">
        <Link to="/hr/custom-reports" className="hrm-report-back">
          <ArrowLeft size={16} aria-hidden />
          Back to Report Studio
        </Link>
        <h1 className="hrm-report-title">{title}</h1>
        {subtitle ? <p className="hrm-report-lead">{subtitle}</p> : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </header>
  );
}
