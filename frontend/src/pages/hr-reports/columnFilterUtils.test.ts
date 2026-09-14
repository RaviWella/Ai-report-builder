import { describe, expect, it } from "vitest";
import { formatReportColumnLabel } from "./columnFilterUtils";

describe("formatReportColumnLabel", () => {
  it("title-cases words and replaces underscores", () => {
    expect(formatReportColumnLabel("emp_no")).toBe("Emp No");
    expect(formatReportColumnLabel("proc_year")).toBe("Year");
    expect(formatReportColumnLabel("proc_month")).toBe("Month");
  });

  it("preserves report acronyms", () => {
    expect(formatReportColumnLabel("ot_1_5_hours")).toBe("OT 1 5 Hours");
    expect(formatReportColumnLabel("total_ot_amount")).toBe("Total OT Amount");
    expect(formatReportColumnLabel("sum_of_ot")).toBe("Sum Of OT");
    expect(formatReportColumnLabel("je")).toBe("JE");
  });
});
