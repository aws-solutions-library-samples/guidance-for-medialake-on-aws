/**
 * Property-based tests for metadata rows ↔ request body round-trip.
 *
 * Feature: collections-custom-metadata
 * Property 6: metadata rows to request body round-trip preserves data
 *
 * Validates: Requirements 6.5, 6.6
 */

import { describe, it, expect } from "vitest";
import fc from "fast-check";

// ---------------------------------------------------------------------------
// Conversion helpers — mirror the exact logic used in Create/Edit modals
// ---------------------------------------------------------------------------

type MetadataRow = { key: string; value: string };

/**
 * Convert a customMetadata object to metadataRows (as done in EditCollectionModal useEffect).
 */
function customMetadataToRows(customMetadata: Record<string, string>): MetadataRow[] {
  return Object.entries(customMetadata).map(([key, value]) => ({ key, value }));
}

/**
 * Convert metadataRows back to a metadata object for the request body
 * (as done in Create/EditCollectionModal handleSubmit).
 * Returns undefined when no valid entries remain (metadata field omitted).
 */
function rowsToRequestMetadata(rows: MetadataRow[]): Record<string, string> | undefined {
  const metadata: Record<string, string> = {};
  rows.forEach((row) => {
    if (row.key.trim()) {
      metadata[row.key.trim()] = row.value.trim();
    }
  });
  return Object.keys(metadata).length > 0 ? metadata : undefined;
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/** Non-empty, already-trimmed key (no leading/trailing whitespace). */
const trimmedNonEmptyKey = fc
  .string({ minLength: 1, maxLength: 30 })
  .map((s) => s.trim())
  .filter((s) => s.length > 0);

/** Arbitrary trimmed string value (may be empty after trim). */
const trimmedValue = fc.string({ maxLength: 50 }).map((s) => s.trim());

/**
 * A customMetadata object with pre-trimmed, non-empty keys and trimmed values.
 * This represents the "canonical" form that should survive a round-trip.
 */
const customMetadataArb = fc
  .array(fc.tuple(trimmedNonEmptyKey, trimmedValue), { minLength: 0, maxLength: 10 })
  .map((entries) => {
    const obj: Record<string, string> = {};
    for (const [k, v] of entries) {
      obj[k] = v; // last-write-wins for duplicate keys, same as Object.entries round-trip
    }
    return obj;
  });

/**
 * A customMetadata object where ALL keys are empty or whitespace-only after trimming.
 */
const allEmptyKeysMetadataArb = fc
  .array(fc.tuple(fc.constantFrom("", " ", "  ", "\t", " \t "), fc.string({ maxLength: 20 })), {
    minLength: 1,
    maxLength: 5,
  })
  .map((entries) => {
    const obj: Record<string, string> = {};
    for (const [k, v] of entries) {
      if (k.length > 0) obj[k] = v;
    }
    return obj;
  })
  .filter((obj) => Object.keys(obj).length > 0); // ensure at least one row exists

// ---------------------------------------------------------------------------
// Property 6: metadata rows to request body round-trip preserves data
// ---------------------------------------------------------------------------

describe("Feature: collections-custom-metadata, Property 6: metadata rows to request body round-trip preserves data", () => {
  /**
   * For any customMetadata object with pre-trimmed non-empty keys and trimmed values,
   * converting to metadataRows and back produces the same key-value pairs.
   *
   * **Validates: Requirements 6.5, 6.6**
   */
  it("round-trip preserves data for canonical (pre-trimmed) metadata", () => {
    fc.assert(
      fc.property(customMetadataArb, (customMetadata) => {
        const rows = customMetadataToRows(customMetadata);
        const result = rowsToRequestMetadata(rows);

        if (Object.keys(customMetadata).length === 0) {
          // Empty input → metadata field omitted
          expect(result).toBeUndefined();
        } else {
          // Non-empty input → same key-value pairs
          expect(result).toEqual(customMetadata);
        }
      }),
      { numRuns: 200 }
    );
  });

  /**
   * When all keys are empty or whitespace-only after trimming,
   * the metadata field is omitted (returns undefined).
   *
   * **Validates: Requirements 6.5, 6.6**
   */
  it("omits metadata field when all keys are empty/whitespace after trimming", () => {
    fc.assert(
      fc.property(allEmptyKeysMetadataArb, (customMetadata) => {
        const rows = customMetadataToRows(customMetadata);
        const result = rowsToRequestMetadata(rows);

        expect(result).toBeUndefined();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Trimming is applied: keys/values with surrounding whitespace in the rows
   * produce trimmed results in the output metadata object.
   *
   * **Validates: Requirements 6.5, 6.6**
   */
  it("keys and values are trimmed during rows-to-metadata conversion", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.tuple(
            fc.string({ minLength: 1, maxLength: 20 }).filter((s) => s.trim().length > 0),
            fc.string({ maxLength: 30 })
          ),
          { minLength: 1, maxLength: 10 }
        ),
        (entries) => {
          // Build rows with potential whitespace
          const rows: MetadataRow[] = entries.map(([k, v]) => ({
            key: `  ${k}  `,
            value: `  ${v}  `,
          }));

          const result = rowsToRequestMetadata(rows);

          // Result should exist (keys are non-empty after trim)
          expect(result).toBeDefined();

          // Every key and value in the result should be trimmed
          for (const [key, value] of Object.entries(result!)) {
            expect(key).toBe(key.trim());
            expect(value).toBe(value.trim());
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
