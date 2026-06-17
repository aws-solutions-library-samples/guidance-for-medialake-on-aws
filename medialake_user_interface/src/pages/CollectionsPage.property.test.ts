/**
 * Property-based tests for metadata chip display logic.
 *
 * Feature: collections-custom-metadata
 * Property 7: metadata chips display correct count with overflow
 *
 * Validates: Requirements 7.1, 7.2, 7.3
 */

import { describe, it, expect } from "vitest";
import fc from "fast-check";

// ---------------------------------------------------------------------------
// Pure computation helper — mirrors the inline logic in CollectionsPage.tsx
// ---------------------------------------------------------------------------

interface ChipDisplay {
  chips: string[];
  overflow: string | null;
}

/**
 * Compute the chip display for a collection's customMetadata.
 * Returns the list of chip labels and an optional overflow label.
 * Returns null when no chips should be rendered (0 entries or null/undefined input).
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

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/** A non-empty metadata key. */
const metadataKey = fc.string({ minLength: 1, maxLength: 20 }).filter((s) => s.length > 0);

/** A metadata value (may be empty). */
const metadataValue = fc.string({ maxLength: 30 });

/**
 * Generate a customMetadata object with exactly `n` unique entries.
 * Uses a set-based approach to guarantee uniqueness.
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

/** Metadata with 1-3 entries. */
const smallMetadataArb = fc.integer({ min: 1, max: 3 }).chain(metadataWithExactCount);

/** Metadata with >3 entries (4-15). */
const largeMetadataArb = fc.integer({ min: 4, max: 15 }).chain(metadataWithExactCount);

/** Metadata with 0+ entries (general). */
const anyMetadataArb = fc.integer({ min: 0, max: 15 }).chain(metadataWithExactCount);

// ---------------------------------------------------------------------------
// Property 7: metadata chips display correct count with overflow
// ---------------------------------------------------------------------------

describe("Feature: collections-custom-metadata, Property 7: metadata chips display correct count with overflow", () => {
  /**
   * When customMetadata is null or undefined, no chips section is rendered.
   *
   * **Validates: Requirements 7.1, 7.2, 7.3**
   */
  it("returns null for null or undefined customMetadata", () => {
    expect(computeChipDisplay(null)).toBeNull();
    expect(computeChipDisplay(undefined)).toBeNull();
  });

  /**
   * When customMetadata is an empty object, no chips section is rendered.
   *
   * **Validates: Requirements 7.1, 7.2, 7.3**
   */
  it("returns null for empty customMetadata", () => {
    expect(computeChipDisplay({})).toBeNull();
  });

  /**
   * For any collection with 1-3 metadata entries, the card renders exactly n chips
   * and no overflow indicator.
   *
   * **Validates: Requirements 7.1, 7.2, 7.3**
   */
  it("renders exactly n chips with no overflow when n is between 1 and 3", () => {
    fc.assert(
      fc.property(smallMetadataArb, (metadata) => {
        const n = Object.keys(metadata).length;
        const result = computeChipDisplay(metadata);

        expect(result).not.toBeNull();
        expect(result!.chips).toHaveLength(n);
        expect(result!.overflow).toBeNull();
      }),
      { numRuns: 200 }
    );
  });

  /**
   * For any collection with >3 metadata entries, the card renders exactly 3 chips
   * plus one overflow chip showing `+{n-3}`.
   *
   * **Validates: Requirements 7.1, 7.2, 7.3**
   */
  it("renders 3 chips plus overflow +{n-3} when n > 3", () => {
    fc.assert(
      fc.property(largeMetadataArb, (metadata) => {
        const n = Object.keys(metadata).length;
        const result = computeChipDisplay(metadata);

        expect(result).not.toBeNull();
        expect(result!.chips).toHaveLength(3);
        expect(result!.overflow).toBe(`+${n - 3}`);
      }),
      { numRuns: 200 }
    );
  });

  /**
   * For any metadata, each chip label is formatted as "key: value".
   *
   * **Validates: Requirements 7.1, 7.2, 7.3**
   */
  it("chip labels are formatted as 'key: value'", () => {
    fc.assert(
      fc.property(
        anyMetadataArb.filter((m) => Object.keys(m).length > 0),
        (metadata) => {
          const result = computeChipDisplay(metadata);
          const entries = Object.entries(metadata);

          expect(result).not.toBeNull();
          result!.chips.forEach((chip, i) => {
            expect(chip).toBe(`${entries[i][0]}: ${entries[i][1]}`);
          });
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * General property: for any n >= 0, chip count is min(n, 3) and overflow is
   * present iff n > 3.
   *
   * **Validates: Requirements 7.1, 7.2, 7.3**
   */
  it("chip count equals min(n, 3) and overflow present iff n > 3", () => {
    fc.assert(
      fc.property(anyMetadataArb, (metadata) => {
        const n = Object.keys(metadata).length;
        const result = computeChipDisplay(metadata);

        if (n === 0) {
          expect(result).toBeNull();
        } else {
          expect(result).not.toBeNull();
          expect(result!.chips).toHaveLength(Math.min(n, 3));
          if (n > 3) {
            expect(result!.overflow).toBe(`+${n - 3}`);
          } else {
            expect(result!.overflow).toBeNull();
          }
        }
      }),
      { numRuns: 300 }
    );
  });
});
