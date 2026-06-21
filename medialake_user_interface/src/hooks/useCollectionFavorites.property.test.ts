/**
 * Property-based tests for the collection-favorites hook.
 *
 * Feature: collection-favorites
 * Property 3: Toggle dispatches add when not favorited and remove when favorited
 *   **Validates: Requirements 1.4, 1.5, 2.4**
 * Property 4: Membership state stays consistent with the favorites cache across operations
 *   **Validates: Requirements 5.1, 5.2**
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import fc from "fast-check";
import type { Favorite } from "../api/hooks/useFavorites";

// Mock the favorites API hooks so the dispatch decision can be observed without
// a network layer or QueryClient. Property 4 below uses extracted pure logic and
// is unaffected by this mock (it never imports the real hooks at runtime).
vi.mock("../api/hooks/useFavorites", () => ({
  useGetFavorites: vi.fn(),
  useAddFavorite: vi.fn(),
  useRemoveFavorite: vi.fn(),
}));

import { useGetFavorites, useAddFavorite, useRemoveFavorite } from "../api/hooks/useFavorites";
import { useCollectionFavorites } from "./useCollectionFavorites";

// ---------------------------------------------------------------------------
// Pure logic extracted from useCollectionFavorites — mirrors the hook's behavior
// ---------------------------------------------------------------------------

const ITEM_TYPE = "COLLECTION" as const;

/**
 * The membership predicate used by the hook: returns true iff the id
 * is present in the favorites array.
 */
function isCollectionFavorited(favorites: Favorite[], collectionId: string): boolean {
  return favorites.some((favorite) => favorite.itemId === collectionId);
}

/**
 * Simulates the optimistic add mutation: appends a new Favorite to the array
 * if not already present (mirrors useAddFavorite's onMutate).
 */
function applyAdd(favorites: Favorite[], collectionId: string): Favorite[] {
  if (favorites.some((fav) => fav.itemId === collectionId)) {
    return favorites;
  }
  return [
    ...favorites,
    {
      itemId: collectionId,
      itemType: ITEM_TYPE,
      metadata: { name: collectionId },
      addedAt: new Date().toISOString(),
    },
  ];
}

/**
 * Simulates the optimistic remove mutation: filters out the Favorite with the
 * given id (mirrors useRemoveFavorite's onMutate).
 */
function applyRemove(favorites: Favorite[], collectionId: string): Favorite[] {
  return favorites.filter((fav) => fav.itemId !== collectionId);
}

// ---------------------------------------------------------------------------
// Operation type for the property test
// ---------------------------------------------------------------------------

interface AddOp {
  type: "add";
  collectionId: string;
}

interface RemoveOp {
  type: "remove";
  collectionId: string;
}

type FavoritesOp = AddOp | RemoveOp;

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/** A collection id (short readable strings). */
const collectionIdArb = fc
  .string({ minLength: 1, maxLength: 12 })
  .filter((s) => s.trim().length > 0);

/** An initial set of favorited collection ids. */
const initialFavoritesArb = fc.uniqueArray(collectionIdArb, { minLength: 0, maxLength: 10 });

/** A single add or remove operation targeting a collection id from a known pool. */
function operationArb(idPool: string[]): fc.Arbitrary<FavoritesOp> {
  if (idPool.length === 0) {
    // When pool is empty, generate a fresh id for an add operation
    return collectionIdArb.map((id) => ({ type: "add" as const, collectionId: id }));
  }
  return fc.oneof(
    // Add an existing id (no-op or re-add)
    fc.constantFrom(...idPool).map((id) => ({ type: "add" as const, collectionId: id })),
    // Add a new id
    collectionIdArb.map((id) => ({ type: "add" as const, collectionId: id })),
    // Remove an existing id
    fc.constantFrom(...idPool).map((id) => ({ type: "remove" as const, collectionId: id })),
    // Remove an id not in pool (no-op)
    collectionIdArb.map((id) => ({ type: "remove" as const, collectionId: id }))
  );
}

/** A sequence of add/remove operations with mixed known and unknown ids. */
const operationSequenceArb = initialFavoritesArb.chain((initialIds) => {
  // Build a pool of ids that might appear in operations: initial + some new ones
  const poolArb = fc
    .uniqueArray(collectionIdArb, { minLength: 0, maxLength: 5 })
    .map((extra) => [...new Set([...initialIds, ...extra])]);
  return poolArb.chain((pool) =>
    fc.tuple(fc.constant(initialIds), fc.array(operationArb(pool), { minLength: 1, maxLength: 20 }))
  );
});

// ---------------------------------------------------------------------------
// Property 4: Membership state stays consistent with the favorites cache
// across operations
// ---------------------------------------------------------------------------

describe("Feature: collection-favorites, Property 4: Membership state stays consistent with the favorites cache across operations", () => {
  /**
   * For any initial favorited-id set and any sequence of add/remove operations,
   * `isCollectionFavorited(id)` after each operation equals whether `id` is in
   * the resulting favorites set — so every surface deriving its toggle state
   * from the predicate shows the same state.
   *
   * **Validates: Requirements 5.1, 5.2**
   */
  it("isCollectionFavorited(id) reflects actual set membership after every operation in a random sequence", () => {
    fc.assert(
      fc.property(operationSequenceArb, ([initialIds, operations]) => {
        // Build initial favorites array from the initial id set
        let favorites: Favorite[] = initialIds.map((id) => ({
          itemId: id,
          itemType: ITEM_TYPE,
          metadata: { name: id },
          addedAt: new Date().toISOString(),
        }));

        // Track the expected membership set in parallel
        const membershipSet = new Set<string>(initialIds);

        // Apply each operation and verify consistency after each step
        for (const op of operations) {
          if (op.type === "add") {
            favorites = applyAdd(favorites, op.collectionId);
            membershipSet.add(op.collectionId);
          } else {
            favorites = applyRemove(favorites, op.collectionId);
            membershipSet.delete(op.collectionId);
          }

          // After each step, verify that isCollectionFavorited matches set membership
          // for the operation's target id
          const predicateResult = isCollectionFavorited(favorites, op.collectionId);
          const setMembership = membershipSet.has(op.collectionId);
          expect(predicateResult).toBe(setMembership);
        }
      }),
      { numRuns: 150 }
    );
  });

  /**
   * Stronger variant: after applying the full sequence, isCollectionFavorited
   * is consistent for ALL ids that were ever involved (not just the last-operated id).
   *
   * **Validates: Requirements 5.1, 5.2**
   */
  it("isCollectionFavorited(id) is consistent for all known ids after a full operation sequence", () => {
    fc.assert(
      fc.property(operationSequenceArb, ([initialIds, operations]) => {
        // Build initial favorites array
        let favorites: Favorite[] = initialIds.map((id) => ({
          itemId: id,
          itemType: ITEM_TYPE,
          metadata: { name: id },
          addedAt: new Date().toISOString(),
        }));

        // Track the expected membership set
        const membershipSet = new Set<string>(initialIds);

        // Collect all ids that have been referenced
        const allIds = new Set<string>(initialIds);

        // Apply all operations
        for (const op of operations) {
          allIds.add(op.collectionId);
          if (op.type === "add") {
            favorites = applyAdd(favorites, op.collectionId);
            membershipSet.add(op.collectionId);
          } else {
            favorites = applyRemove(favorites, op.collectionId);
            membershipSet.delete(op.collectionId);
          }
        }

        // After all operations, verify consistency for every id ever seen
        for (const id of allIds) {
          const predicateResult = isCollectionFavorited(favorites, id);
          const setMembership = membershipSet.has(id);
          expect(predicateResult).toBe(setMembership);
        }
      }),
      { numRuns: 150 }
    );
  });

  /**
   * Adding an id then removing it results in not-favorited state;
   * removing then adding results in favorited state — for any id.
   *
   * **Validates: Requirements 5.1, 5.2**
   */
  it("add-then-remove yields not-favorited; remove-then-add yields favorited", () => {
    fc.assert(
      fc.property(initialFavoritesArb, collectionIdArb, (initialIds, targetId) => {
        // Initial state
        let favorites: Favorite[] = initialIds.map((id) => ({
          itemId: id,
          itemType: ITEM_TYPE,
          metadata: { name: id },
          addedAt: new Date().toISOString(),
        }));

        // Add then remove
        favorites = applyAdd(favorites, targetId);
        expect(isCollectionFavorited(favorites, targetId)).toBe(true);

        favorites = applyRemove(favorites, targetId);
        expect(isCollectionFavorited(favorites, targetId)).toBe(false);

        // Remove then add (starting from not-favorited state)
        favorites = applyRemove(favorites, targetId);
        expect(isCollectionFavorited(favorites, targetId)).toBe(false);

        favorites = applyAdd(favorites, targetId);
        expect(isCollectionFavorited(favorites, targetId)).toBe(true);
      }),
      { numRuns: 150 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 3: Toggle dispatches add when not favorited and remove when favorited
//
// Exercises the REAL useCollectionFavorites hook with the favorites API hooks
// mocked, so we observe exactly which mutation it dispatches and with what
// arguments. **Validates: Requirements 1.4, 1.5, 2.4**
// ---------------------------------------------------------------------------

const mockedUseGetFavorites = vi.mocked(useGetFavorites);
const mockedUseAddFavorite = vi.mocked(useAddFavorite);
const mockedUseRemoveFavorite = vi.mocked(useRemoveFavorite);

/** A target collection passed to handleFavoriteToggle. */
const collectionArb = fc.record({
  id: collectionIdArb,
  name: fc.string({ maxLength: 20 }),
  isPublic: fc.boolean(),
  itemCount: fc.nat({ max: 1000 }),
  childCollectionCount: fc.nat({ max: 100 }),
});

describe("Feature: collection-favorites, Property 3: Toggle dispatches add when not favorited and remove when favorited", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("dispatches add (not favorited) or remove (favorited) with itemType=COLLECTION and the collection id", () => {
    fc.assert(
      fc.property(initialFavoritesArb, collectionArb, (favoritedIds, collection) => {
        const addMutate = vi.fn();
        const removeMutate = vi.fn();
        const stopPropagation = vi.fn();

        const favorites: Favorite[] = favoritedIds.map((id) => ({
          itemId: id,
          itemType: ITEM_TYPE,
          metadata: { name: id },
          addedAt: "2024-01-01T00:00:00Z",
        }));

        mockedUseGetFavorites.mockReturnValue({ data: favorites } as ReturnType<
          typeof useGetFavorites
        >);
        mockedUseAddFavorite.mockReturnValue({ mutate: addMutate } as unknown as ReturnType<
          typeof useAddFavorite
        >);
        mockedUseRemoveFavorite.mockReturnValue({ mutate: removeMutate } as unknown as ReturnType<
          typeof useRemoveFavorite
        >);

        const { result } = renderHook(() => useCollectionFavorites());

        const event = { stopPropagation } as unknown as Parameters<
          typeof result.current.handleFavoriteToggle
        >[1];
        result.current.handleFavoriteToggle(collection, event);

        // The toggle must never let the click bubble to card navigation (Req 1.8).
        expect(stopPropagation).toHaveBeenCalledTimes(1);

        const isFavorited = favoritedIds.includes(collection.id);
        if (isFavorited) {
          expect(removeMutate).toHaveBeenCalledTimes(1);
          expect(removeMutate).toHaveBeenCalledWith({
            itemType: "COLLECTION",
            itemId: collection.id,
          });
          expect(addMutate).not.toHaveBeenCalled();
        } else {
          expect(addMutate).toHaveBeenCalledTimes(1);
          const addArg = addMutate.mock.calls[0][0];
          expect(addArg.itemType).toBe("COLLECTION");
          expect(addArg.itemId).toBe(collection.id);
          expect(addArg.metadata.name).toBe(collection.name);
          expect(removeMutate).not.toHaveBeenCalled();
        }
      }),
      { numRuns: 150 }
    );
  });
});
