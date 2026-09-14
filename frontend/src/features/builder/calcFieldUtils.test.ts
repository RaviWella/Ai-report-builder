import { describe, expect, it } from "vitest";
import {
  formulaTokenAt,
  insertFormulaRef,
  matchFormulaFields,
} from "./calcFieldUtils";
import type { SemanticFieldMeta } from "../../types/spec";

const field = (
  ref: string,
  label: string,
  entity = "payroll",
): SemanticFieldMeta => ({
  ref, label, entity, type: "decimal", role: "measure", allowed_aggregations: ["sum"],
});

describe("formulaTokenAt", () => {
  it("reads the identifier under the caret", () => {
    expect(formulaTokenAt("payroll.gr", 10)).toEqual({ start: 0, end: 10, text: "payroll.gr" });
    expect(formulaTokenAt("payroll.net - bas", 17)).toEqual({ start: 14, end: 17, text: "bas" });
    expect(formulaTokenAt("a + b", 1)).toEqual({ start: 0, end: 1, text: "a" });
  });

  it("treats arithmetic and grouping as token boundaries", () => {
    expect(formulaTokenAt("net-(bas", 8).text).toBe("bas");
    expect(formulaTokenAt("gross × ot", 10).text).toBe("ot");
  });

  it("returns an empty token after a separator", () => {
    expect(formulaTokenAt("payroll.net - ", 14)).toEqual({ start: 14, end: 14, text: "" });
  });
});

describe("insertFormulaRef", () => {
  it("replaces the partial token with the field ref", () => {
    expect(insertFormulaRef("bas", 3, "payroll.basic")).toEqual({
      next: "payroll.basic",
      caret: 13,
    });
    expect(insertFormulaRef("payroll.net - bas", 17, "payroll.basic")).toEqual({
      next: "payroll.net - payroll.basic",
      caret: 27,
    });
  });

  it("inserts at the caret when the current token is empty", () => {
    expect(insertFormulaRef("payroll.net - ", 14, "payroll.basic")).toEqual({
      next: "payroll.net - payroll.basic",
      caret: 27,
    });
  });
});

describe("matchFormulaFields", () => {
  const fields = [
    field("payroll.basic", "Basic Salary"),
    field("payroll.net", "Net Salary"),
    field("attendance.ot_hours", "Overtime Hours", "attendance"),
  ];

  it("matches label, ref, or entity", () => {
    expect(matchFormulaFields(fields, "basic").map((f) => f.ref)).toEqual(["payroll.basic"]);
    expect(matchFormulaFields(fields, "net").map((f) => f.ref)).toEqual(["payroll.net"]);
    expect(matchFormulaFields(fields, "attendance").map((f) => f.ref)).toEqual(["attendance.ot_hours"]);
  });

  it("returns nothing for a blank query", () => {
    expect(matchFormulaFields(fields, "  ")).toEqual([]);
  });
});
