import { describe, expect, it } from "vitest";
import { isFaintColor, normalizeWordMergeHtml, sanitizeLetterHtml, wordMarksKey } from "./letterHtml";

describe("letterHtml", () => {
  it("treats near-white Word colours as faint", () => {
    expect(isFaintColor("#F2F2F2")).toBe(true);
    expect(isFaintColor("#BFBFBF")).toBe(true);
    expect(isFaintColor("white")).toBe(true);
    expect(isFaintColor("silver")).toBe(true);
    expect(isFaintColor("rgb(255, 255, 255)")).toBe(true);
    expect(isFaintColor("rgba(0, 0, 0, 0.15)")).toBe(true);
    expect(isFaintColor("#1F2937")).toBe(false);
    expect(isFaintColor("black")).toBe(false);
    expect(isFaintColor("#007499")).toBe(false);
  });

  it("strips faint colours from Word merge fields and tokens, keeps real ink", () => {
    const html = [
      '<p>HRIS: <span style="color:#F2F2F2;font-weight:bold">«HRIS»</span></p>',
      '<p>Dear <span style="color: #BFBFBF">{{attendance_daily.display_name}}</span></p>',
      '<p><span style="color:#1F2937">Acceptance of Resignation</span></p>',
    ].join("");
    const out = sanitizeLetterHtml(html);
    expect(out).toContain("«HRIS»");
    expect(out).toContain("{{attendance_daily.display_name}}");
    expect(out).not.toContain("color:#F2F2F2");
    expect(out).not.toContain("color: #BFBFBF");
    expect(out).toContain("font-weight:bold");
    expect(out).toContain("color:#1F2937");
  });

  it("finds merge names in « » or << >>; entity decode does not invent marks", () => {
    expect(normalizeWordMergeHtml("&laquo;Date&raquo;")).toBe("«Date»");
    expect(normalizeWordMergeHtml("<<HRIS>>")).toBe("<<HRIS>>");
    expect(wordMarksKey("&laquo;Date&raquo; and <<HRIS>>")).toBe("<<HRIS>>|«Date»");
  });
});
