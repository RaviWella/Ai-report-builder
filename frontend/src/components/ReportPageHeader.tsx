import type { ReactNode } from "react";

interface ReportPageHeaderProps {
  title: string;
  description?: ReactNode;
  children?: ReactNode;
}

export default function ReportPageHeader({
  title,
  description,
  children,
}: ReportPageHeaderProps) {
  return (
    <header className="hrm-report-header">
      <div className="min-w-0">
        <h1 className="hrm-report-title">{title}</h1>
        {description ? <p className="hrm-report-lead">{description}</p> : null}
      </div>
      {children}
    </header>
  );
}
