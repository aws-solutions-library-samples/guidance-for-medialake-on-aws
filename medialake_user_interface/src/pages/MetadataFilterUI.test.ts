/**
 * Unit tests for metadata filter UI logic — dropdown population and filter computation.
 *
 * Since CollectionsPage.tsx has many dependencies (routing, auth, API hooks, etc.),
 * we test the filter logic as pure computation rather than rendering the full page.
 *
 * Validates: Requirements 9.1, 9.2, 9.3
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Pure computation helper — mirrors the inline logic in CollectionsPage.tsx:
//
//   const activeMetadataFilters = metadataFilterKey && metadataFilterValue
//     ? { [metadataFilterKey]: metadataFilterValue }
//     : undefined;
// ---------------------------------------------------------------------------

/**
 * Compute active metadata filters from the selected key and entered value.
 * Returns the filter object when both key and value are non-empty,
 * or undefined when either is missing.
 *
 * **Validates: Requirements 9.2, 9.3**
 */
function computeActiveMetadataFilters(
  key: string,
  value: string
): Record<string, string> | undefined {
  return key && value ? { [key]: value } : undefined;
}

/**
 * Extract metadata keys from the API response shape.
 * Mirrors: `const metadataKeys = metadataKeysResponse?.data?.keys || [];`
 *
 * **Validates: Requirements 9.1, 9.2**
 */
function extractMetadataKeys(
  response: { data?: { keys?: string[] } } | null | undefined
): string[] {
  return response?.data?.keys || [];
}

// ---------------------------------------------------------------------------
// computeActiveMetadataFilters — filter computation
// ---------------------------------------------------------------------------

describe("computeActiveMetadataFilters", () => {
  /**
   * **Validates: Requirement 9.3**
   */
  it("returns undefined when both key and value are empty", () => {
    expect(computeActiveMetadataFilters("", "")).toBeUndefined();
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns undefined when key is selected but value is empty", () => {
    expect(computeActiveMetadataFilters("project", "")).toBeUndefined();
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns undefined when value is entered but no key is selected", () => {
    expect(computeActiveMetadataFilters("", "alpha")).toBeUndefined();
  });

  /**
   * **Validates: Requirement 9.3**
   */
  it("returns filter object when both key and value are provided", () => {
    expect(computeActiveMetadataFilters("project", "alpha")).toEqual({
      project: "alpha",
    });
  });

  /**
   * **Validates: Requirement 9.3**
   */
  it("uses the key as the object property name", () => {
    const result = computeActiveMetadataFilters("department", "engineering");
    expect(result).toEqual({ department: "engineering" });
    expect(Object.keys(result!)).toEqual(["department"]);
  });

  /**
   * **Validates: Requirement 9.3**
   */
  it("handles keys with special characters", () => {
    const result = computeActiveMetadataFilters("my-key_v2", "some value");
    expect(result).toEqual({ "my-key_v2": "some value" });
  });

  /**
   * **Validates: Requirement 9.3**
   */
  it("preserves whitespace in values (trimming is a UI concern)", () => {
    const result = computeActiveMetadataFilters("tag", " spaced ");
    expect(result).toEqual({ tag: " spaced " });
  });
});

// ---------------------------------------------------------------------------
// extractMetadataKeys — dropdown population from API response
// ---------------------------------------------------------------------------

describe("extractMetadataKeys", () => {
  /**
   * **Validates: Requirement 9.1**
   */
  it("extracts keys from a valid API response", () => {
    const response = { data: { keys: ["department", "project", "region"] } };
    expect(extractMetadataKeys(response)).toEqual(["department", "project", "region"]);
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns empty array when response is null", () => {
    expect(extractMetadataKeys(null)).toEqual([]);
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns empty array when response is undefined", () => {
    expect(extractMetadataKeys(undefined)).toEqual([]);
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns empty array when data is missing", () => {
    expect(extractMetadataKeys({})).toEqual([]);
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns empty array when keys is missing", () => {
    expect(extractMetadataKeys({ data: {} })).toEqual([]);
  });

  /**
   * **Validates: Requirement 9.2**
   */
  it("returns empty array when keys list is empty", () => {
    expect(extractMetadataKeys({ data: { keys: [] } })).toEqual([]);
  });

  /**
   * **Validates: Requirement 9.1**
   */
  it("preserves the order of keys from the API response", () => {
    const response = { data: { keys: ["z-key", "a-key", "m-key"] } };
    expect(extractMetadataKeys(response)).toEqual(["z-key", "a-key", "m-key"]);
  });
});
