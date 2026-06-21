import { describe, expect, it } from "vitest";

import type { EditorSection } from "../../stores/usePortalEditorStore";
import {
  ALL_GROUPED_SECTIONS,
  SECTION_GROUPS,
  countGroupErrors,
  groupOfSection,
} from "./sectionGroups";

/**
 * Every member of the {@link EditorSection} union. Kept explicit (rather than
 * derived) so that adding a section to the store union without grouping it
 * here makes this test fail loudly — that is the whole point of the
 * single-source-of-truth check below.
 */
const EXPECTED_SECTIONS: readonly EditorSection[] = [
  "branding",
  "content",
  "appearance",
  "typography",
  "layout",
  "access",
  "destinations",
  "metadata",
  "pages",
  "fields",
];

describe("sectionGroups", () => {
  it("assigns every EditorSection to exactly one group (no orphans, no duplicates)", () => {
    expect([...ALL_GROUPED_SECTIONS].sort()).toEqual([...EXPECTED_SECTIONS].sort());
    // No section appears in more than one group.
    expect(new Set(ALL_GROUPED_SECTIONS).size).toBe(ALL_GROUPED_SECTIONS.length);
  });

  it("groups appearance sections as exactly the PortalAppearance shape", () => {
    const appearance = SECTION_GROUPS.find((g) => g.key === "appearance");
    expect(appearance?.sections).toEqual([
      "branding",
      "content",
      "appearance",
      "typography",
      "layout",
    ]);
  });

  it("groups structure sections as exactly what a Template layers on", () => {
    const structure = SECTION_GROUPS.find((g) => g.key === "structure");
    expect(structure?.sections).toEqual(["pages", "fields", "destinations", "access", "metadata"]);
  });

  it("maps each section back to its owning group", () => {
    expect(groupOfSection("branding")).toBe("appearance");
    expect(groupOfSection("typography")).toBe("appearance");
    expect(groupOfSection("pages")).toBe("structure");
    expect(groupOfSection("access")).toBe("structure");
  });

  it("rolls up validation error counts per group", () => {
    const validationErrors = {
      // structure group
      pages: [{ field: "destinations", message: "needs a destination" }],
      access: [{ field: "allowedGroups", message: "pick at least one group" }],
      // appearance group
      typography: [{ field: "bodyFont", message: "invalid font" }],
    };

    expect(countGroupErrors("structure", validationErrors)).toBe(2);
    expect(countGroupErrors("appearance", validationErrors)).toBe(1);
  });

  it("returns 0 for a group with no recorded errors", () => {
    expect(countGroupErrors("appearance", {})).toBe(0);
    expect(countGroupErrors("structure", { branding: [{ field: "x", message: "y" }] })).toBe(0);
  });
});
