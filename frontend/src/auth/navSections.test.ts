import { describe, expect, it } from "vitest";
import {
  DEFAULT_NAV_SECTION_FLAGS,
  isSectionAllowed,
  resolveNavFlags,
  sectionForPath,
} from "./navSections";

describe("sectionForPath", () => {
  it("maps sidebar sections without implying a route lock", () => {
    expect(sectionForPath("/")).toBe("Templates");
    expect(sectionForPath("/chat")).toBe("Chat");
    expect(sectionForPath("/builder/abc")).toBe("Builder");
    expect(sectionForPath("/rule-reports/new")).toBe("Builder");
    expect(sectionForPath("/documents")).toBe("Documents");
    expect(sectionForPath("/documents/report/new")).toBe("Documents");
    expect(sectionForPath("/viewer")).toBe("Viewer");
    expect(sectionForPath("/viewer/r/1")).toBe("Viewer");
    expect(sectionForPath("/how-it-works")).toBe("How it works");
    expect(sectionForPath("/settings/permissions")).toBeNull();
  });
});

describe("isSectionAllowed", () => {
  it("defaults Documents/Viewer on and never allows Config/AI Settings", () => {
    expect(isSectionAllowed(undefined, "Templates")).toBe(true);
    expect(isSectionAllowed(undefined, "Documents")).toBe(true);
    expect(isSectionAllowed(null, "Viewer")).toBe(true);
    expect(isSectionAllowed(null, "Chat")).toBe(false);
    expect(isSectionAllowed({ Config: true, "AI Settings": true }, "Config")).toBe(false);
    expect(isSectionAllowed({ "AI Settings": true }, "AI Settings")).toBe(false);
    expect(DEFAULT_NAV_SECTION_FLAGS).not.toHaveProperty("Config");
    expect(DEFAULT_NAV_SECTION_FLAGS).not.toHaveProperty("AI Settings");
  });

  it("respects grantable flags for sidebar visibility only", () => {
    const flags = resolveNavFlags({
      Chat: true,
      Builder: true,
      Documents: true,
      Viewer: false,
      "How it works": false,
    });
    expect(isSectionAllowed(flags, "Chat")).toBe(true);
    expect(isSectionAllowed(flags, "Viewer")).toBe(false);
  });
});
