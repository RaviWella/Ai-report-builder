import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

interface ReportCrossLinkProps {
  to: string;
  children: ReactNode;
}

export default function ReportCrossLink({ to, children }: ReportCrossLinkProps) {
  return (
    <p>
      <Link
        to={to}
        className="inline-flex items-center gap-1 text-sm font-medium text-teal-800 hover:text-teal-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600"
      >
        {children}
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </p>
  );
}
