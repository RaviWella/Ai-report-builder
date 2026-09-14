import type { CustomReportView } from "../services/api";

/** Sidebar-aligned sections for customized report listings. */
export const CUSTOM_REPORT_SECTIONS = [
  {
    id: "employment",
    title: "Employment",
    modules: ["employment"],
  },
  {
    id: "operations",
    title: "Operations",
    modules: ["payroll", "attendance", "leave", "performance"],
  },
] as const;

/** Display order for customized report list sections (each module is a top-level category). */
export const CUSTOM_REPORT_DISPLAY_MODULES = [
  "employment",
  ...CUSTOM_REPORT_SECTIONS.find((section) => section.id === "operations")!.modules,
] as const;

const MODULE_LABELS: Record<string, string> = {
  employment: "Employment",
  payroll: "Payroll",
  attendance: "Attendance",
  leave: "Leave",
  performance: "Performance",
};

export function moduleLabel(module: string): string {
  return (
    MODULE_LABELS[module.toLowerCase()] ??
    module.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export const REPORT_SQL_HELP =
  "Write a SELECT query against your HR mart tables. Use tokens below for schema names and tenant ID.";

export type CustomReportDisplaySection = {
  id: string;
  title: string;
  views: CustomReportView[];
};

function bucketViewsByModule(views: CustomReportView[]): Map<string, CustomReportView[]> {
  const buckets = new Map<string, CustomReportView[]>();
  for (const view of views) {
    const mod = (view.module ?? "").trim().toLowerCase() || "other";
    const list = buckets.get(mod) ?? [];
    list.push(view);
    buckets.set(mod, list);
  }
  return buckets;
}

/** Group customized reports by module: Employment, Payroll, Leave, etc. as top-level sections. */
export function groupCustomReportsForDisplay(
  views: CustomReportView[],
): CustomReportDisplaySection[] {
  const byModule = bucketViewsByModule(views);
  const sections: CustomReportDisplaySection[] = [];

  for (const mod of CUSTOM_REPORT_DISPLAY_MODULES) {
    const modViews = byModule.get(mod);
    if (modViews?.length) {
      sections.push({
        id: mod,
        title: moduleLabel(mod),
        views: modViews,
      });
      byModule.delete(mod);
    }
  }

  const otherViews: CustomReportView[] = [];
  for (const modViews of byModule.values()) {
    otherViews.push(...modViews);
  }
  if (otherViews.length > 0) {
    sections.push({
      id: "other",
      title: "Other",
      views: otherViews,
    });
  }

  return sections;
}
