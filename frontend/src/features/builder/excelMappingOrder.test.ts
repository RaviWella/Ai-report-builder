import { describe, expect, it } from "vitest";
import {
  buildMappingDisplayRows,
  extraAfterFromRows,
  moveExtraInRows,
  reportOrderFromRows,
} from "./excelMappingOrder";

const headers = ["NIC Number", "Surname", "Total Earnings"];

describe("buildMappingDisplayRows", () => {
  it("keeps extras after the last sheet column when no slot is stored", () => {
    const rows = buildMappingDisplayRows(headers, ["calc.total_contribution"], {});
    expect(rows.map((r) => (r.kind === "mapped" ? r.header : r.ref))).toEqual([
      "NIC Number",
      "Surname",
      "Total Earnings",
      "calc.total_contribution",
    ]);
  });

  it("slots an extra between mapped columns", () => {
    const rows = buildMappingDisplayRows(headers, ["calc.total_contribution"], {
      "calc.total_contribution": "Surname",
    });
    expect(rows.map((r) => (r.kind === "mapped" ? r.header : r.ref))).toEqual([
      "NIC Number",
      "Surname",
      "calc.total_contribution",
      "Total Earnings",
    ]);
  });

  it("places an extra before the first sheet column", () => {
    const rows = buildMappingDisplayRows(headers, ["calc.x"], { "calc.x": null });
    expect(rows[0]).toEqual({ kind: "extra", ref: "calc.x" });
  });
});

describe("moveExtraInRows", () => {
  it("moves an extra up between mapped columns", () => {
    const start = buildMappingDisplayRows(headers, ["calc.x"], {});
    const moved = moveExtraInRows(start, "calc.x", -1);
    expect(moved).not.toBeNull();
    expect(extraAfterFromRows(moved!)).toEqual({ "calc.x": "Surname" });
  });

  it("returns null at the top", () => {
    const start = buildMappingDisplayRows(headers, ["calc.x"], { "calc.x": null });
    expect(moveExtraInRows(start, "calc.x", -1)).toBeNull();
  });
});

describe("reportOrderFromRows", () => {
  it("follows visual order for added mapped + extra fields", () => {
    const rows = buildMappingDisplayRows(headers, ["calc.x"], { "calc.x": "NIC Number" });
    const order = reportOrderFromRows(
      rows,
      {
        "NIC Number": "employee.nic",
        Surname: "employee.surname",
        "Total Earnings": "payroll.gross",
      },
      ["employee.nic", "calc.x", "payroll.gross"],
    );
    expect(order).toEqual(["employee.nic", "calc.x", "payroll.gross"]);
  });
});
