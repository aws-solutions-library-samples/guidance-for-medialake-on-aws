/**
 * Unit tests for metadata display logic — card chips and detail page table.
 *
 * These example-based tests complement the property-based tests in
 * CollectionsPage.property.test.ts (Property 7) and
 * CollectionViewPage.property.test.ts (Property 8).
 *
 * Validates: Requirements 7.1, 7.2, 7.3, 8.1, 8.2
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Pure computation helpers — same logic as in the property test files,
// mirroring the inline rendering logic in the page components.
// ---------------------------------------------------------------------------

interface ChipDisplay {
  chips: string[];
  overflow: string | null;
}

/**
 * Compute chip display for a collection card.
 * **Validates: Requirements 7.1, 7.2, 7.3**
 */
function computeChipDisplay(
  customMetadata: Record<string, string> | null | undefined
): ChipDisplay | null {
  const entries = Object.entries(customMetadata || {});
  if (entries.length === 0) return null;
  const displayEntries = entries.slice(0, 3);
  const overflowCount = entries.length - 3;
  return {
    chips: displayEntries.map(([k, v]) => `${k}: ${v}`),
    overflow: overflowCount > 0 ? `+${overflowCount}` : null,
  };
}

interface TableEntry {
  key: string;
  value: string;
}

/**
 * Compute table display for the detail page.
 * **Validates: Requirements 8.1, 8.2**
 */
function computeTableDisplay(
  customMetadata: Record<string, string> | null | undefined
): TableEntry[] | null {
  const entries = Object.entries(customMetadata || {});
  if (entries.length === 0) return null;
  return entries.map(([key, value]) => ({ key, value }));
}

// ---------------------------------------------------------------------------
// Card Chips — concrete examples
// ---------------------------------------------------------------------------

describe("Card chips display", () => {
  /**
   * **Validates: Requirement 7.3**
   */
  it("returns null when customMetadata is null", () => {
    expect(computeChipDisplay(null)).toBeNull();
  });

  /**
   * **Validates: Requirement 7.3**
   */
  it("returns null when customMetadata is undefined", () => {
    expect(computeChipDisplay(undefined)).toBeNull();
  });

  /**
   * **Validates: Requirement 7.3**
   */
  it("returns null when customMetadata is an empty object", () => {
    expect(computeChipDisplay({})).toBeNull();
  });

  /**
   * **Validates: Requirement 7.1**
   */
  it("renders 1 chip for a single metadata entry", () => {
    const result = computeChipDisplay({ project: "alpha" });
    expect(result).toEqual({
      chips: ["project: alpha"],
      overflow: null,
    });
  });

  /**
   * **Validates: Requirement 7.1**
   */
  it("renders 3 chips for exactly 3 metadata entries", () => {
    const result = computeChipDisplay({
      project: "alpha",
      region: "us-west-2",
      team: "platform",
    });
    expect(result).toEqual({
      chips: ["project: alpha", "region: us-west-2", "team: platform"],
      overflow: null,
    });
  });

  /**
   * **Validates: Requirements 7.1, 7.2**
   */
  it("renders 3 chips plus overflow for 5 metadata entries", () => {
    const result = computeChipDisplay({
      project: "alpha",
      region: "us-west-2",
      team: "platform",
      env: "production",
      owner: "jane",
    });
    expect(result).not.toBeNull();
    expect(result!.chips).toHaveLength(3);
    expect(result!.overflow).toBe("+2");
  });

  /**
   * **Validates: Requirement 7.2**
   */
  it("overflow text follows +{n-3} format for 4 entries", () => {
    const result = computeChipDisplay({
      a: "1",
      b: "2",
      c: "3",
      d: "4",
    });
    expect(result!.chips).toHaveLength(3);
    expect(result!.overflow).toBe("+1");
  });
});

// ---------------------------------------------------------------------------
// Detail Page Table — concrete examples
// ---------------------------------------------------------------------------

describe("Detail page metadata table", () => {
  /**
   * **Validates: Requirement 8.2**
   */
  it("returns null when customMetadata is null", () => {
    expect(computeTableDisplay(null)).toBeNull();
  });

  /**
   * **Validates: Requirement 8.2**
   */
  it("returns null when customMetadata is undefined", () => {
    expect(computeTableDisplay(undefined)).toBeNull();
  });

  /**
   * **Validates: Requirement 8.2**
   */
  it("returns null when customMetadata is an empty object", () => {
    expect(computeTableDisplay({})).toBeNull();
  });

  /**
   * **Validates: Requirement 8.1**
   */
  it("renders a single row for one metadata entry", () => {
    const result = computeTableDisplay({ project: "alpha" });
    expect(result).toEqual([{ key: "project", value: "alpha" }]);
  });

  /**
   * **Validates: Requirement 8.1**
   */
  it("renders all rows for multiple metadata entries", () => {
    const metadata = {
      project: "alpha",
      region: "us-west-2",
      team: "platform",
      env: "production",
    };
    const result = computeTableDisplay(metadata);
    expect(result).toHaveLength(4);
    expect(result).toEqual([
      { key: "project", value: "alpha" },
      { key: "region", value: "us-west-2" },
      { key: "team", value: "platform" },
      { key: "env", value: "production" },
    ]);
  });

  /**
   * **Validates: Requirement 8.1**
   */
  it("preserves metadata values including empty strings", () => {
    const result = computeTableDisplay({ tag: "" });
    expect(result).toEqual([{ key: "tag", value: "" }]);
  });
});
