import { useEffect } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Users,
  TrendingDown,
  DollarSign,
  Clock,
  Calendar,
  Star,
  TableProperties,
  Database,
  Layers,
  LayoutDashboard,
  BadgeDollarSign,
  GitBranch,
  UserCircle,
  FileSpreadsheet,
} from "lucide-react";
import clsx from "clsx";
import type { LucideIcon } from "lucide-react";
import { hasFullNavAccess } from "../lib/activeTenant";
import { getTenantBranding } from "../lib/tenantBranding";

type NavItem = { to: string; label: string; icon: LucideIcon };
type NavSection = { title?: string; items: NavItem[]; variant?: "solo" | "platform" | "default" };

const DASHBOARD_SECTION: NavSection = {
  variant: "solo",
  items: [{ to: "/hr/dashboard", label: "Dashboard", icon: LayoutDashboard }],
};

const REPORT_SECTIONS: NavSection[] = [
  {
    title: "Employment",
    items: [
      { to: "/hr/headcount", label: "Headcount & movement", icon: Users },
      { to: "/hr/employees", label: "Employees", icon: UserCircle },
      { to: "/hr/salary-bands", label: "Salary bands", icon: BadgeDollarSign },
      { to: "/hr/lifecycle", label: "Lifecycle", icon: GitBranch },
      { to: "/hr/turnover", label: "Turnover & attrition", icon: TrendingDown },
    ],
  },
  {
    title: "Operations",
    items: [
      { to: "/hr/payroll", label: "Payroll", icon: DollarSign },
      { to: "/hr/attendance", label: "Attendance", icon: Clock },
      { to: "/hr/leave", label: "Leave", icon: Calendar },
      { to: "/hr/performance", label: "Performance", icon: Star },
      { to: "/hr/custom-reports", label: "Report Studio", icon: FileSpreadsheet },
    ],
  },
];

const PLATFORM_SECTION: NavSection = {
  variant: "platform",
  title: "Platform",
  items: [
    { to: "/datamart/chat", label: "Datamart Assistant", icon: TableProperties },
    { to: "/etl/control", label: "ETL Control", icon: Database },
    { to: "/settings/custom-reports", label: "Report Studio Config", icon: FileSpreadsheet },
    { to: "/settings/etl-sources", label: "Source databases", icon: Layers },
  ],
};

const CUSTOM_REPORTS_SECTION: NavSection = {
  variant: "solo",
  items: [{ to: "/hr/custom-reports", label: "Report Studio", icon: FileSpreadsheet }],
};

function isCustomReportsPath(pathname: string): boolean {
  return pathname === "/hr/custom-reports" || pathname.startsWith("/hr/custom-reports/");
}

function isNavItemActive(to: string, pathname: string, isActive: boolean): boolean {
  if (to === "/datamart/chat") return pathname.startsWith("/datamart");
  if (to === "/hr/custom-reports") return pathname.startsWith("/hr/custom-reports");
  if (to === "/settings/custom-reports") return pathname.startsWith("/settings/custom-reports");
  return isActive;
}

function NavSectionBlock({ section }: { section: NavSection }) {
  const location = useLocation();

  return (
    <div
      className={clsx(
        "hrm-shell-nav-section",
        section.variant === "solo" && "hrm-shell-nav-section--solo",
        section.variant === "platform" && "hrm-shell-nav-section--platform",
      )}
    >
      {section.title ? <p className="hrm-shell-nav-label">{section.title}</p> : null}
      {section.items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/hr/dashboard"}
          className={({ isActive }) =>
            clsx(
              "hrm-shell-nav-link",
              isNavItemActive(to, location.pathname, isActive) && "hrm-shell-nav-link--active",
            )
          }
        >
          <Icon size={16} className="hrm-shell-nav-icon" aria-hidden />
          <span className="hrm-shell-nav-link__text">{label}</span>
        </NavLink>
      ))}
    </div>
  );
}

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const fullNav = hasFullNavAccess();
  const isDatamart = location.pathname.startsWith("/datamart");
  const branding = getTenantBranding();
  const logoUrl = branding?.logo_url?.trim();
  const companyName = branding?.company_name?.trim();

  useEffect(() => {
    if (fullNav || isCustomReportsPath(location.pathname)) return;
    navigate("/hr/custom-reports", { replace: true });
  }, [fullNav, location.pathname, navigate]);

  return (
    <div className="hrm-shell">
      <aside className="hrm-shell-sidebar" aria-label="Application">
        <div className="hrm-shell-brand">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={companyName ? `${companyName} logo` : "Company logo"}
              className="h-10 w-auto max-w-[148px] object-contain object-left"
            />
          ) : companyName ? (
            <>
              <span className="hrm-shell-brand__mark" aria-hidden />
              <span className="hrm-shell-brand__tenant">{companyName}</span>
            </>
          ) : (
            <>
              <span className="hrm-shell-brand__mark" aria-hidden />
              <span className="hrm-shell-brand__name">MintHRM</span>
            </>
          )}
        </div>

        <nav className="hrm-shell-nav" aria-label="Primary">
          {fullNav ? (
            <>
              <NavSectionBlock section={DASHBOARD_SECTION} />

              <div className="hrm-shell-nav-scroll">
                {REPORT_SECTIONS.map((section, si) => (
                  <NavSectionBlock key={si} section={section} />
                ))}
              </div>

              <NavSectionBlock section={PLATFORM_SECTION} />
            </>
          ) : (
            <NavSectionBlock section={CUSTOM_REPORTS_SECTION} />
          )}
        </nav>

        <div className="hrm-shell-footer">HR Intelligence Platform</div>
      </aside>

      <main
        className={clsx(
          "hrm-shell-main",
          isDatamart ? "hrm-shell-main--locked" : "hrm-shell-main--scroll",
        )}
      >
        <Outlet />
      </main>
    </div>
  );
}
