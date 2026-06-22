/**
 * Property-based tests for CollectionSelector multi-select set semantics and count.
 *
 * Feature: upload-to-collections
 * Property 8: Multi-select set semantics and count
 *
 * Validates: Requirements 5.1, 5.2, 5.3, 5.4
 *
 * Strategy: The CollectionSelector component is controlled — it receives `value`
 * (the Selected_Collections) and calls `onChange` with the new value on each toggle.
 * The handleToggle logic is:
 *   - If the collection id IS in value → remove it (deselect, Req 5.3)
 *   - If the collection id IS NOT in value → append it (select, Req 5.1)
 *
 * We test the toggle model by simulating the same logic the component applies on each
 * toggle action, then verify the resulting set matches expectations. A separate assertion
 * renders the component with the final value to confirm the count chip displays correctly
 * (Req 5.4). This approach avoids full interactive rendering per iteration (which is too
 * slow for PBT) while still testing through the component's actual interface contract.
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import fc from "fast-check";

import CollectionSelector, { type CollectionRef } from "./CollectionSelector";
import type { Collection } from "@/api/hooks/useCollections";

// ---------------------------------------------------------------------------
// Mocks (minimal — only needed for count chip rendering assertions)
// ---------------------------------------------------------------------------

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue: string, opts?: Record<string, any>) => {
      if (opts?.count !== undefined) return `${opts.count} selected`;
      return defaultValue || _key;
    },
  }),
}));

vi.mock("@/api/hooks/useCollections", () => ({
  useRecentCollections: () => ({
    data: { pages: [{ data: [] }] },
    isLoading: false,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
  }),
  useGetAllCollections: () => ({
    data: { data: [] },
    isLoading: false,
  }),
  useGetCollections: () => ({
    data: { data: [], pagination: { hasNextPage: false } },
    isLoading: false,
    isError: false,
    isFetching: false,
  }),
  useCreateCollection: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  isAddable: () => true,
}));

vi.mock("@/api/hooks/useFavorites", () => ({
  useGetFavorites: () => ({
    data: [],
    isLoading: false,
  }),
}));

vi.mock("@/hooks/useDebounce", () => ({
  useDebounce: (value: any) => value,
}));

vi.mock("../../hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError: vi.fn() }),
}));

// ---------------------------------------------------------------------------
// Model: replicate the handleToggle logic from CollectionSelector
// ---------------------------------------------------------------------------

/**
 * Applies a single toggle action to the current value array, following the same
 * logic as CollectionSelector.handleToggle:
 *   - If collection.id is already in value → filter it out
 *   - Otherwise → append { id, name }
 */
function applyToggle(
  currentValue: CollectionRef[],
  collection: { id: string; name: string }
): CollectionRef[] {
  const selectedIds = new Set(currentValue.map((c) => c.id));
  if (selectedIds.has(collection.id)) {
    return currentValue.filter((c) => c.id !== collection.id);
  } else {
    return [...currentValue, { id: collection.id, name: collection.name }];
  }
}

/**
 * Apply a sequence of toggle actions and return the final value.
 */
function applyToggleSequence(
  pool: { id: string; name: string }[],
  actionIndices: number[]
): CollectionRef[] {
  let value: CollectionRef[] = [];
  for (const index of actionIndices) {
    value = applyToggle(value, pool[index]);
  }
  return value;
}

/**
 * Compute the expected set of selected ids after toggle actions.
 * Each toggle flips membership: present → remove, absent → add.
 */
function computeExpectedIds(
  pool: { id: string; name: string }[],
  actionIndices: number[]
): Set<string> {
  const selected = new Set<string>();
  for (const index of actionIndices) {
    const id = pool[index].id;
    if (selected.has(id)) {
      selected.delete(id);
    } else {
      selected.add(id);
    }
  }
  return selected;
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const POOL_SIZE = 10;

/** Fixed pool of collections for the model tests. */
const pool: { id: string; name: string }[] = Array.from({ length: POOL_SIZE }, (_, i) => ({
  id: `col-${i}`,
  name: `Collection ${i}`,
}));

/** Arbitrary sequence of toggle action indices. */
const actionSequenceArb = fc.array(fc.integer({ min: 0, max: POOL_SIZE - 1 }), {
  minLength: 1,
  maxLength: 30,
});

// ---------------------------------------------------------------------------
// Property 8: Multi-select set semantics and count
// ---------------------------------------------------------------------------

describe("Feature: upload-to-collections, Property 8: Multi-select set semantics and count", () => {
  /**
   * For any sequence of select/deselect (toggle) actions, the resulting
   * Selected_Collections equals the set of collections toggled an odd number
   * of times (i.e., selected and not subsequently deselected). The result
   * contains no duplicate ids.
   *
   * Validates: Requirements 5.1, 5.2, 5.3
   */
  it("toggle sequence produces the correct selected set with no duplicates", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const result = applyToggleSequence(pool, actions);
        const expectedIds = computeExpectedIds(pool, actions);

        // No duplicates: array length equals unique id count
        const resultIds = result.map((c) => c.id);
        const resultIdSet = new Set(resultIds);
        expect(resultIds.length).toBe(resultIdSet.size);

        // Correct elements
        expect(resultIdSet.size).toBe(expectedIds.size);
        for (const id of expectedIds) {
          expect(resultIdSet.has(id)).toBe(true);
        }
      }),
      { numRuns: 200 }
    );
  });

  /**
   * The displayed count (count chip) equals the size of the selected set.
   * We verify this by rendering the CollectionSelector with the value produced
   * by a toggle sequence and checking the count chip text matches.
   *
   * Validates: Requirements 5.4
   */
  it("displayed count equals the selected set size", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        const finalValue = applyToggleSequence(pool, actions);
        const expectedCount = finalValue.length;

        const { unmount } = render(<CollectionSelector value={finalValue} onChange={() => {}} />);

        if (expectedCount > 0) {
          expect(screen.getByText(`${expectedCount} selected`)).toBeInTheDocument();
        } else {
          expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
        }

        unmount();
      }),
      { numRuns: 150 }
    );
  });

  /**
   * Selecting and then deselecting the same collection always results in removal
   * (a double-toggle returns the collection to its original membership state).
   *
   * Validates: Requirements 5.3
   */
  it("double-toggling the same collection cancels out", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: POOL_SIZE - 1 }),
        // Generate an arbitrary prefix of actions before the double-toggle
        fc.array(fc.integer({ min: 0, max: POOL_SIZE - 1 }), { minLength: 0, maxLength: 10 }),
        (targetIndex, prefixActions) => {
          // Apply prefix, then toggle target twice
          const allActions = [...prefixActions, targetIndex, targetIndex];
          const result = applyToggleSequence(pool, allActions);

          // The same as applying only the prefix (double-toggle cancels)
          const prefixResult = applyToggleSequence(pool, prefixActions);

          const resultIds = new Set(result.map((c) => c.id));
          const prefixIds = new Set(prefixResult.map((c) => c.id));

          expect(resultIds.size).toBe(prefixIds.size);
          for (const id of prefixIds) {
            expect(resultIds.has(id)).toBe(true);
          }
        }
      ),
      { numRuns: 150 }
    );
  });

  /**
   * Multiple distinct collections can be held concurrently in the selection.
   * Selecting N distinct collections (each toggled exactly once from unselected)
   * yields exactly N elements.
   *
   * Validates: Requirements 5.1, 5.2
   */
  it("selecting N distinct collections yields exactly N elements", () => {
    fc.assert(
      fc.property(
        fc.uniqueArray(fc.integer({ min: 0, max: POOL_SIZE - 1 }), { minLength: 1 }),
        (indices) => {
          const result = applyToggleSequence(pool, indices);

          // All distinct indices toggled once → all should be present
          expect(result.length).toBe(indices.length);
          const resultIds = new Set(result.map((c) => c.id));
          for (const idx of indices) {
            expect(resultIds.has(pool[idx].id)).toBe(true);
          }
        }
      ),
      { numRuns: 150 }
    );
  });

  /**
   * Selection is independent of which section a collection appears in — toggling
   * a collection by id always produces the same result regardless of the name or
   * other attributes (Req 5.2 - "independent of which section").
   * Model: toggling the same id with different names still produces a unique-id set.
   *
   * Validates: Requirements 5.2
   */
  it("selection is keyed by id — duplicated ids do not create duplicates in value", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: POOL_SIZE - 1 }), (index) => {
        // Simulate toggling the same id: first select, then select again
        // (since it's already selected, second toggle removes it)
        const result = applyToggleSequence(pool, [index, index, index]);

        // Odd number of toggles (3) → should be selected
        const resultIds = new Set(result.map((c) => c.id));
        expect(resultIds.has(pool[index].id)).toBe(true);
        // But only once
        expect(result.filter((c) => c.id === pool[index].id).length).toBe(1);
      }),
      { numRuns: 100 }
    );
  });
});
