import { describe, expect, it } from "vitest";
import type { CustomReportView } from "../services/api";
import { groupCustomReportsForDisplay } from "./customReportModules";

function view(
  view_name: string,
  module: string,
  label = view_name,
): CustomReportView {
  return { view_name, label, schema: "custom_reports", module };
}

describe("groupCustomReportsForDisplay", () => {
  it("uses each module as a top-level section", () => {
    const sections = groupCustomReportsForDisplay([
      view("vw_payroll_a", "payroll", "Payroll A"),
      view("vw_leave_a", "leave", "Leave A"),
      view("vw_payroll_b", "payroll", "Payroll B"),
    ]);

    expect(sections.map((s) => s.id)).toEqual(["payroll", "leave"]);
    expect(sections[0].title).toBe("Payroll");
    expect(sections[0].views).toHaveLength(2);
    expect(sections[1].views).toHaveLength(1);
  });

  it("orders Employment before Payroll", () => {
    const sections = groupCustomReportsForDisplay([
      view("vw_pay", "payroll"),
      view("vw_emp", "employment"),
    ]);

    expect(sections.map((s) => s.id)).toEqual(["employment", "payroll"]);
  });

  it("omits modules with no reports", () => {
    const sections = groupCustomReportsForDisplay([view("vw_pay", "payroll")]);
    expect(sections).toHaveLength(1);
    expect(sections[0].id).toBe("payroll");
  });
});
