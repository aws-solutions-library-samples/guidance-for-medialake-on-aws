/**
 * Property-based tests for metadata table display logic on the detail page.
 *
 * Feature: collections-custom-metadata
 * Property 8: detail page renders complete metadata table
 *
 * Validates: Requirements 8.1, 8.2
 */

import { describe, it, expect } from "vitest";
import fc from "fast-check";

// ---------------------------------------------------------------------------
// Pure computation helper — mirrors the inline logic in CollectionViewPage.tsx
// ---------------------------------------------------------------------------

interface TableEntry {
  key: string;
  value: string;
}

/**
 * Compute the table display for a collection's customMetadata.
 * Returns an array of { key, value } entries when metadata has entries,
 * or null when no table should be rendered (null/undefined/empty input).
 */
function computeTableDisplay(
  customMetadata: Record<string, string> | null | undefined
): TableEntry[] | null {
  const entries = Object.entries(customMetadata || {});
  if (entries.length === 0) return null;
  return entries.map(([key, value]) => ({ key, value }));
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/** A non-empty metadata key. */
const metadataKey = fc.string({ minLength: 1, maxLength: 20 }).filter((s) => s.length > 0);

/** A metadata value (may be empty). */
const metadataValue = fc.string({ maxLength: 30 });

/**
 * Generate a customMetadata object with exactly `n` unique entries.
 */
function metadataWithExactCount(n: number) {
  return fc.uniqueArray(metadataKey, { minLength: n, maxLength: n }).chain((keys) =>
    fc.tuple(...keys.map(() => metadataValue)).map((values) => {
      const obj: Record<string, string> = {};
      keys.forEach((k, i) => {
        obj[k] = values[i];
      });
      return obj;
    })
  );
}

/** Metadata with 1+ entries (1-20). */
const nonEmptyMetadataArb = fc.integer({ min: 1, max: 20 }).chain(metadataWithExactCount);

/** Metadata with 0+ entries (general). */
const anyMetadataArb = fc.integer({ min: 0, max: 20 }).chain(metadataWithExactCount);

// ---------------------------------------------------------------------------
// Property 8: detail page renders complete metadata table
// ---------------------------------------------------------------------------

describe("Feature: collections-custom-metadata, Property 8: detail page renders complete metadata table", () => {
  /**
   * When customMetadata is null or undefined, no table is rendered.
   *
   * **Validates: Requirements 8.1, 8.2**
   */
  it("returns null for null or undefined customMetadata", () => {
    expect(computeTableDisplay(null)).toBeNull();
    expect(computeTableDisplay(undefined)).toBeNull();
  });

  /**
   * When customMetadata is an empty object, no table is rendered.
   *
   * **Validates: Requirements 8.1, 8.2**
   */
  it("returns null for empty customMetadata", () => {
    expect(computeTableDisplay({})).toBeNull();
  });

  /**
   * For any collection with one or more metadata entries, the table contains
   * every entry — the row count equals the number of metadata entries.
   *
   * **Validates: Requirements 8.1, 8.2**
   */
  it("table row count equals the number of metadata entries", () => {
    fc.assert(
      fc.property(nonEmptyMetadataArb, (metadata) => {
        const n = Object.keys(metadata).length;
        const result = computeTableDisplay(metadata);

        expect(result).not.toBeNull();
        expect(result).toHaveLength(n);
      }),
      { numRuns: 200 }
    );
  });

  /**
   * For any collection with metadata entries, every key-value pair from the
   * original metadata appears in the table (no entries are truncated or lost).
   *
   * **Validates: Requirements 8.1, 8.2**
   */
  it("table contains every key-value pair from customMetadata", () => {
    fc.assert(
      fc.property(nonEmptyMetadataArb, (metadata) => {
        const result = computeTableDisplay(metadata);

        expect(result).not.toBeNull();
        const resultMap: Record<string, string> = {};
        result!.forEach(({ key, value }) => {
          resultMap[key] = value;
        });

        // Every original entry must be present in the table
        for (const [key, value] of Object.entries(metadata)) {
          expect(resultMap[key]).toBe(value);
        }

        // No extra entries in the table
        expect(Object.keys(resultMap)).toHaveLength(Object.keys(metadata).length);
      }),
      { numRuns: 200 }
    );
  });

  /**
   * General property: for any metadata (including empty), table is rendered
   * iff there is at least one entry, and when rendered it contains all entries.
   *
   * **Validates: Requirements 8.1, 8.2**
   */
  it("table is rendered iff metadata has entries, and contains all of them", () => {
    fc.assert(
      fc.property(anyMetadataArb, (metadata) => {
        const n = Object.keys(metadata).length;
        const result = computeTableDisplay(metadata);

        if (n === 0) {
          expect(result).toBeNull();
        } else {
          expect(result).not.toBeNull();
          expect(result).toHaveLength(n);

          // Verify each entry matches
          const entries = Object.entries(metadata);
          entries.forEach(([key, value], i) => {
            expect(result![i].key).toBe(key);
            expect(result![i].value).toBe(value);
          });
        }
      }),
      { numRuns: 300 }
    );
  });
});
