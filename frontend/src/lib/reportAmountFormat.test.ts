import { describe, expect, it } from "vitest";
import {
  formatReportAmount,
  formatReportCellValue,
  isReportAmountColumn,
} from "./reportAmountFormat";

describe("reportAmountFormat", () => {
  it("detects amount columns", () => {
    expect(isReportAmountColumn("basic_salary")).toBe(true);
    expect(isReportAmountColumn("ot_1_5_amount")).toBe(true);
    expect(isReportAmountColumn("amount")).toBe(true);
    expect(isReportAmountColumn("proc_year")).toBe(false);
    expect(isReportAmountColumn("count_of_emp_no")).toBe(false);
  });

  it("formats amounts with commas and two decimals", () => {
    expect(formatReportAmount(10000)).toBe("10,000.00");
    expect(formatReportAmount(1234.5)).toBe("1,234.50");
    expect(formatReportAmount(null)).toBe("—");
  });

  it("formats report cells by column type", () => {
    expect(formatReportCellValue("total_ot_amount", 10000)).toBe("10,000.00");
    expect(formatReportCellValue("proc_year", 2026)).toBe("2026");
  });
});
