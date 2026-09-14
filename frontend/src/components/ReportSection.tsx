import type { ReactNode } from "react";

interface ReportSectionProps {
  title: string;
  children: ReactNode;
}

export default function ReportSection({ title, children }: ReportSectionProps) {
  return (
    <section className="hrm-report-section">
      <h2 className="hrm-report-section-title">{title}</h2>
      {children}
    </section>
  );
}
