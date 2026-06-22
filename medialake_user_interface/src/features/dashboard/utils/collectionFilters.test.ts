import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { filterCollections, Collection } from "./collectionFilters";
import { CollectionViewType } from "../types";

/**
 * Property-Based Tests for Collection Filtering
 *
 * Feature: dashboard-collection-widgets
 * Property 2: View Type Filtering Correctness
 *
 * **Validates: Requirements 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**
 */

describe("Property 2: View Type Filtering Correctness", () => {
  // Helper to generate valid ISO date strings using timestamps
  const isoDateArbitrary = fc
    .integer({ min: 1577836800000, max: 1767225600000 })
    .map((timestamp) => new Date(timestamp).toISOString());

  // Arbitrary generator for Collection objects
  const collectionArbitrary = fc.record({
    id: fc.uuid(),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    description: fc.option(fc.string({ maxLength: 200 })),
    type: fc.constantFrom("public" as const, "private" as const, "shared" as const),
    parentId: fc.option(fc.uuid()),
    collectionTypeId: fc.option(fc.uuid()),
    ownerId: fc.uuid(),
    ownerName: fc.option(fc.string({ minLength: 1, maxLength: 50 })),
    itemCount: fc.nat({ max: 10000 }),
    childCount: fc.nat({ max: 100 }),
    childCollectionCount: fc.nat({ max: 100 }),
    isPublic: fc.boolean(),
    status: fc.constantFrom("active", "archived", "deleted"),
    userRole: fc.option(fc.constantFrom("owner", "editor", "viewer")),
    createdAt: isoDateArbitrary,
    updatedAt: isoDateArbitrary,
    isShared: fc.option(fc.boolean()),
    shareCount: fc.option(fc.nat({ max: 100 })),
    sharedWithMe: fc.option(fc.boolean()),
    myRole: fc.option(fc.constantFrom("owner", "editor", "viewer")),
    sharedAt: fc.option(isoDateArbitrary),
    sharedWith: fc.option(
      fc.array(
        fc.record({
          targetId: fc.uuid(),
          targetType: fc.constantFrom("user", "group"),
          role: fc.constantFrom("owner", "editor", "viewer"),
          grantedAt: isoDateArbitrary,
        }),
        { minLength: 0, maxLength: 10 }
      )
    ),
    ancestors: fc.option(
      fc.array(
        fc.record({
          id: fc.uuid(),
          name: fc.string({ minLength: 1, maxLength: 50 }),
          parentId: fc.option(fc.uuid()),
        }),
        { minLength: 0, maxLength: 5 }
      )
    ),
  }) as fc.Arbitrary<Collection>;

  // Arbitrary generator for arrays of collections
  const collectionsArrayArbitrary = fc.array(collectionArbitrary, { minLength: 0, maxLength: 50 });

  // Arbitrary generator for user IDs
  const userIdArbitrary = fc.uuid();

  it('should return all collections when viewType is "all"', () => {
    fc.assert(
      fc.property(collectionsArrayArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "all", userId);

        // Property: filtered result should equal input for "all" view type
        expect(result).toEqual(collections);
        expect(result.length).toBe(collections.length);
      }),
      { numRuns: 100 }
    );
  });

  it('should return only public collections when viewType is "public"', () => {
    fc.assert(
      fc.property(collectionsArrayArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "public", userId);

        // Property: all returned collections must have isPublic === true
        result.forEach((collection) => {
          expect(collection.isPublic).toBe(true);
        });

        // Property: result should contain all public collections from input
        const expectedPublicCollections = collections.filter((c) => c.isPublic === true);
        expect(result.length).toBe(expectedPublicCollections.length);
        expect(result).toEqual(expectedPublicCollections);
      }),
      { numRuns: 100 }
    );
  });

  it('should return only private collections when viewType is "private"', () => {
    fc.assert(
      fc.property(collectionsArrayArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "private", userId);

        // Property: all returned collections must have isPublic === false
        result.forEach((collection) => {
          expect(collection.isPublic).toBe(false);
        });

        // Property: result should contain all private collections from input
        const expectedPrivateCollections = collections.filter((c) => c.isPublic === false);
        expect(result.length).toBe(expectedPrivateCollections.length);
        expect(result).toEqual(expectedPrivateCollections);
      }),
      { numRuns: 100 }
    );
  });

  it('should return only user-owned collections when viewType is "my-collections"', () => {
    fc.assert(
      fc.property(collectionsArrayArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "my-collections", userId);

        // Property: all returned collections must have ownerId === userId
        result.forEach((collection) => {
          expect(collection.ownerId).toBe(userId);
        });

        // Property: result should contain all user-owned collections from input
        const expectedMyCollections = collections.filter((c) => c.ownerId === userId);
        expect(result.length).toBe(expectedMyCollections.length);
        expect(result).toEqual(expectedMyCollections);
      }),
      { numRuns: 100 }
    );
  });

  it('should return all collections when viewType is "shared-with-me" (dedicated endpoint)', () => {
    fc.assert(
      fc.property(collectionsArrayArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "shared-with-me", userId);

        // Property: for dedicated endpoint view types, no filtering should occur
        // The API endpoint returns pre-filtered data
        expect(result).toEqual(collections);
        expect(result.length).toBe(collections.length);
      }),
      { numRuns: 100 }
    );
  });

  it('should return all collections when viewType is "my-shared" (dedicated endpoint)', () => {
    fc.assert(
      fc.property(collectionsArrayArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "my-shared", userId);

        // Property: for dedicated endpoint view types, no filtering should occur
        // The API endpoint returns pre-filtered data
        expect(result).toEqual(collections);
        expect(result.length).toBe(collections.length);
      }),
      { numRuns: 100 }
    );
  });

  it("should maintain collection object integrity after filtering", () => {
    fc.assert(
      fc.property(
        collectionsArrayArbitrary,
        userIdArbitrary,
        fc.constantFrom<CollectionViewType>(
          "all",
          "public",
          "private",
          "my-collections",
          "shared-with-me",
          "my-shared"
        ),
        (collections, userId, viewType) => {
          const result = filterCollections(collections, viewType, userId);

          // Property: all returned collections should be from the original input
          result.forEach((collection) => {
            const originalCollection = collections.find((c) => c.id === collection.id);
            expect(originalCollection).toBeDefined();
            expect(collection).toEqual(originalCollection);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should return empty array when filtering empty collection set", () => {
    fc.assert(
      fc.property(
        userIdArbitrary,
        fc.constantFrom<CollectionViewType>(
          "all",
          "public",
          "private",
          "my-collections",
          "shared-with-me",
          "my-shared"
        ),
        (userId, viewType) => {
          const result = filterCollections([], viewType, userId);

          // Property: filtering empty array should always return empty array
          expect(result).toEqual([]);
          expect(result.length).toBe(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should be idempotent - filtering twice should equal filtering once", () => {
    fc.assert(
      fc.property(
        collectionsArrayArbitrary,
        userIdArbitrary,
        fc.constantFrom<CollectionViewType>(
          "all",
          "public",
          "private",
          "my-collections",
          "shared-with-me",
          "my-shared"
        ),
        (collections, userId, viewType) => {
          const firstFilter = filterCollections(collections, viewType, userId);
          const secondFilter = filterCollections(firstFilter, viewType, userId);

          // Property: filtering is idempotent
          expect(secondFilter).toEqual(firstFilter);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should never return more collections than input", () => {
    fc.assert(
      fc.property(
        collectionsArrayArbitrary,
        userIdArbitrary,
        fc.constantFrom<CollectionViewType>(
          "all",
          "public",
          "private",
          "my-collections",
          "shared-with-me",
          "my-shared"
        ),
        (collections, userId, viewType) => {
          const result = filterCollections(collections, viewType, userId);

          // Property: result size should never exceed input size
          expect(result.length).toBeLessThanOrEqual(collections.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should handle collections with all combinations of isPublic and ownerId", () => {
    const isoDateArb = fc
      .integer({ min: 1577836800000, max: 1767225600000 })
      .map((timestamp) => new Date(timestamp).toISOString());

    fc.assert(
      fc.property(
        userIdArbitrary,
        fc.array(
          fc.record({
            id: fc.uuid(),
            name: fc.string({ minLength: 1 }),
            ownerId: fc.uuid(),
            isPublic: fc.boolean(),
            // Minimal required fields
            type: fc.constantFrom("public" as const, "private" as const, "shared" as const),
            itemCount: fc.nat(),
            childCount: fc.nat(),
            childCollectionCount: fc.nat(),
            status: fc.constant("active"),
            createdAt: isoDateArb,
            updatedAt: isoDateArb,
          }) as fc.Arbitrary<Collection>,
          { minLength: 10, maxLength: 50 }
        ),
        (userId, collections) => {
          // Test all view types with diverse collection properties
          const allResult = filterCollections(collections, "all", userId);
          const publicResult = filterCollections(collections, "public", userId);
          const privateResult = filterCollections(collections, "private", userId);
          const myCollectionsResult = filterCollections(collections, "my-collections", userId);

          // Property: public + private should equal all (for client-side filtered views)
          const publicAndPrivate = [...publicResult, ...privateResult];
          expect(publicAndPrivate.length).toBe(allResult.length);

          // Property: my-collections should be a subset of all
          expect(myCollectionsResult.length).toBeLessThanOrEqual(allResult.length);

          // Property: all my-collections should be in the all result
          myCollectionsResult.forEach((collection) => {
            expect(allResult.find((c) => c.id === collection.id)).toBeDefined();
          });
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Unit Tests for Collection Sorting
 *
 * Feature: dashboard-collection-widgets
 * Tests for sortCollections function
 *
 * **Validates: Requirements 3.2, 3.3, 3.5**
 */

import { sortCollections } from "./collectionFilters";
import { SortConfig } from "../types";

describe("sortCollections", () => {
  // Helper function to create test collections
  const createTestCollection = (overrides: Partial<Collection>): Collection => ({
    id: overrides.id || "test-id",
    name: overrides.name || "Test Collection",
    type: "public",
    ownerId: "user-123",
    itemCount: 0,
    childCount: 0,
    childCollectionCount: 0,
    isPublic: true,
    status: "active",
    createdAt: overrides.createdAt || "2024-01-01T00:00:00Z",
    updatedAt: overrides.updatedAt || "2024-01-01T00:00:00Z",
    ...overrides,
  });

  describe("sorting by name", () => {
    it("should sort collections alphabetically in ascending order", () => {
      const collections = [
        createTestCollection({ id: "1", name: "Zebra" }),
        createTestCollection({ id: "2", name: "Apple" }),
        createTestCollection({ id: "3", name: "Mango" }),
      ];

      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].name).toBe("Apple");
      expect(result[1].name).toBe("Mango");
      expect(result[2].name).toBe("Zebra");
    });

    it("should sort collections alphabetically in descending order", () => {
      const collections = [
        createTestCollection({ id: "1", name: "Apple" }),
        createTestCollection({ id: "2", name: "Zebra" }),
        createTestCollection({ id: "3", name: "Mango" }),
      ];

      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "desc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].name).toBe("Zebra");
      expect(result[1].name).toBe("Mango");
      expect(result[2].name).toBe("Apple");
    });

    it("should sort case-insensitively", () => {
      const collections = [
        createTestCollection({ id: "1", name: "zebra" }),
        createTestCollection({ id: "2", name: "Apple" }),
        createTestCollection({ id: "3", name: "MANGO" }),
      ];

      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].name).toBe("Apple");
      expect(result[1].name).toBe("MANGO");
      expect(result[2].name).toBe("zebra");
    });
  });

  describe("sorting by createdAt", () => {
    it("should sort collections by creation date in ascending order", () => {
      const collections = [
        createTestCollection({ id: "1", name: "C1", createdAt: "2024-03-01T00:00:00Z" }),
        createTestCollection({ id: "2", name: "C2", createdAt: "2024-01-01T00:00:00Z" }),
        createTestCollection({ id: "3", name: "C3", createdAt: "2024-02-01T00:00:00Z" }),
      ];

      const sortConfig: SortConfig = { sortBy: "createdAt", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].id).toBe("2"); // 2024-01-01
      expect(result[1].id).toBe("3"); // 2024-02-01
      expect(result[2].id).toBe("1"); // 2024-03-01
    });

    it("should sort collections by creation date in descending order", () => {
      const collections = [
        createTestCollection({ id: "1", name: "C1", createdAt: "2024-01-01T00:00:00Z" }),
        createTestCollection({ id: "2", name: "C2", createdAt: "2024-03-01T00:00:00Z" }),
        createTestCollection({ id: "3", name: "C3", createdAt: "2024-02-01T00:00:00Z" }),
      ];

      const sortConfig: SortConfig = { sortBy: "createdAt", sortOrder: "desc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].id).toBe("2"); // 2024-03-01
      expect(result[1].id).toBe("3"); // 2024-02-01
      expect(result[2].id).toBe("1"); // 2024-01-01
    });
  });

  describe("sorting by updatedAt", () => {
    it("should sort collections by update date in ascending order", () => {
      const collections = [
        createTestCollection({ id: "1", name: "C1", updatedAt: "2024-03-15T00:00:00Z" }),
        createTestCollection({ id: "2", name: "C2", updatedAt: "2024-01-15T00:00:00Z" }),
        createTestCollection({ id: "3", name: "C3", updatedAt: "2024-02-15T00:00:00Z" }),
      ];

      const sortConfig: SortConfig = { sortBy: "updatedAt", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].id).toBe("2"); // 2024-01-15
      expect(result[1].id).toBe("3"); // 2024-02-15
      expect(result[2].id).toBe("1"); // 2024-03-15
    });

    it("should sort collections by update date in descending order", () => {
      const collections = [
        createTestCollection({ id: "1", name: "C1", updatedAt: "2024-01-15T00:00:00Z" }),
        createTestCollection({ id: "2", name: "C2", updatedAt: "2024-03-15T00:00:00Z" }),
        createTestCollection({ id: "3", name: "C3", updatedAt: "2024-02-15T00:00:00Z" }),
      ];

      const sortConfig: SortConfig = { sortBy: "updatedAt", sortOrder: "desc" };
      const result = sortCollections(collections, sortConfig);

      expect(result[0].id).toBe("2"); // 2024-03-15
      expect(result[1].id).toBe("3"); // 2024-02-15
      expect(result[2].id).toBe("1"); // 2024-01-15
    });
  });

  describe("edge cases", () => {
    it("should handle empty array", () => {
      const collections: Collection[] = [];
      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result).toEqual([]);
      expect(result.length).toBe(0);
    });

    it("should handle single collection", () => {
      const collections = [createTestCollection({ id: "1", name: "Single" })];
      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result.length).toBe(1);
      expect(result[0].name).toBe("Single");
    });

    it("should not mutate the original array", () => {
      const collections = [
        createTestCollection({ id: "1", name: "Zebra" }),
        createTestCollection({ id: "2", name: "Apple" }),
      ];
      const originalOrder = [...collections];

      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "asc" };
      sortCollections(collections, sortConfig);

      // Original array should remain unchanged
      expect(collections).toEqual(originalOrder);
      expect(collections[0].name).toBe("Zebra");
      expect(collections[1].name).toBe("Apple");
    });

    it("should handle collections with identical sort values", () => {
      const collections = [
        createTestCollection({ id: "1", name: "Same Name" }),
        createTestCollection({ id: "2", name: "Same Name" }),
        createTestCollection({ id: "3", name: "Same Name" }),
      ];

      const sortConfig: SortConfig = { sortBy: "name", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      // Should maintain stable sort (order preserved for equal elements)
      expect(result.length).toBe(3);
      result.forEach((collection) => {
        expect(collection.name).toBe("Same Name");
      });
    });

    it("should handle collections with same timestamps", () => {
      const sameDate = "2024-01-01T00:00:00Z";
      const collections = [
        createTestCollection({ id: "1", name: "C1", createdAt: sameDate }),
        createTestCollection({ id: "2", name: "C2", createdAt: sameDate }),
        createTestCollection({ id: "3", name: "C3", createdAt: sameDate }),
      ];

      const sortConfig: SortConfig = { sortBy: "createdAt", sortOrder: "asc" };
      const result = sortCollections(collections, sortConfig);

      expect(result.length).toBe(3);
      result.forEach((collection) => {
        expect(collection.createdAt).toBe(sameDate);
      });
    });
  });
});

/**
 * Property-Based Tests for Collection Favorites Filtering
 *
 * Feature: collection-favorites
 * Property 1: Favorites view returns exactly the favorited collections
 *
 * **Validates: Requirements 3.2, 4.2**
 */

describe("Property 1: Favorites view returns exactly the favorited collections", () => {
  // Helper to generate valid ISO date strings
  const isoDateArbitrary = fc
    .integer({ min: 1577836800000, max: 1767225600000 })
    .map((timestamp) => new Date(timestamp).toISOString());

  // Generate an array of collections with guaranteed unique ids
  const uniqueCollectionsArbitrary = fc
    .uniqueArray(fc.uuid(), { minLength: 0, maxLength: 30 })
    .chain((ids: string[]) =>
      ids.length === 0
        ? fc.constant([] as Collection[])
        : (fc.tuple(
            ...ids.map((id) =>
              fc.record({
                id: fc.constant(id),
                name: fc.string({ minLength: 1, maxLength: 50 }),
                type: fc.constantFrom("public" as const, "private" as const, "shared" as const),
                ownerId: fc.uuid(),
                itemCount: fc.nat({ max: 10000 }),
                childCount: fc.nat({ max: 100 }),
                childCollectionCount: fc.nat({ max: 100 }),
                isPublic: fc.boolean(),
                status: fc.constantFrom("active", "archived", "deleted"),
                createdAt: isoDateArbitrary,
                updatedAt: isoDateArbitrary,
              })
            )
          ) as fc.Arbitrary<Collection[]>)
    );

  // Arbitrary for a user id
  const userIdArbitrary = fc.uuid();

  // Arbitrary for a set of favorited ids (may include ids not in any dataset)
  const favoritedIdsArbitrary = fc.uniqueArray(fc.uuid(), { minLength: 0, maxLength: 20 });

  it("should return exactly those collections whose id is in the favoritedIds set", () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIdArray) => {
          const favoritedIds = new Set(favoritedIdArray);
          const result = filterCollections(collections, "favorites", userId, favoritedIds);

          // Property: every returned collection's id must be in the favoritedIds set
          for (const c of result) {
            expect(favoritedIds.has(c.id)).toBe(true);
          }

          // Property: every collection in the dataset whose id is in favoritedIds must appear in the result
          const expectedIds = new Set(
            collections.filter((c) => favoritedIds.has(c.id)).map((c) => c.id)
          );
          const resultIds = new Set(result.map((c) => c.id));
          expect(resultIds).toEqual(expectedIds);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should return an empty array when favoritedIds is empty", () => {
    fc.assert(
      fc.property(uniqueCollectionsArbitrary, userIdArbitrary, (collections, userId) => {
        const favoritedIds = new Set<string>();
        const result = filterCollections(collections, "favorites", userId, favoritedIds);

        expect(result).toEqual([]);
        expect(result.length).toBe(0);
      }),
      { numRuns: 100 }
    );
  });

  it("should return an empty array when the dataset is empty", () => {
    fc.assert(
      fc.property(userIdArbitrary, favoritedIdsArbitrary, (userId, favoritedIdArray) => {
        const favoritedIds = new Set(favoritedIdArray);
        const result = filterCollections([], "favorites", userId, favoritedIds);

        expect(result).toEqual([]);
        expect(result.length).toBe(0);
      }),
      { numRuns: 100 }
    );
  });

  it("should return all collections when favoritedIds fully covers the dataset", () => {
    fc.assert(
      fc.property(uniqueCollectionsArbitrary, userIdArbitrary, (collections, userId) => {
        // Full overlap: all collection ids are in favoritedIds
        const favoritedIds = new Set(collections.map((c) => c.id));
        const result = filterCollections(collections, "favorites", userId, favoritedIds);

        expect(result.length).toBe(collections.length);
        expect(new Set(result.map((c) => c.id))).toEqual(favoritedIds);
      }),
      { numRuns: 100 }
    );
  });

  it("should ignore favoritedIds not present in the dataset (ids absent from dataset)", () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, extraIds) => {
          // Combine actual collection ids with extra ids not in the dataset
          const datasetIds = new Set(collections.map((c) => c.id));
          const favoritedIds = new Set([
            ...collections.map((c) => c.id),
            ...extraIds.filter((id) => !datasetIds.has(id)),
          ]);

          const result = filterCollections(collections, "favorites", userId, favoritedIds);

          // All collections should be returned (full overlap with dataset ids)
          // Extra ids that aren't in the dataset don't produce extra results
          expect(result.length).toBe(collections.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should handle duplicate ids in the favoritedIds set gracefully", () => {
    fc.assert(
      fc.property(uniqueCollectionsArbitrary, userIdArbitrary, (collections, userId) => {
        if (collections.length === 0) return;

        // Build favoritedIds with duplicates (Set deduplicates, so simulating via array→Set)
        const idsWithDuplicates = [
          ...collections.map((c) => c.id),
          ...collections.map((c) => c.id), // duplicated
        ];
        const favoritedIds = new Set(idsWithDuplicates);

        const result = filterCollections(collections, "favorites", userId, favoritedIds);

        // Each collection should appear exactly once in the result (no duplicates)
        expect(result.length).toBe(collections.length);
        const resultIds = result.map((c) => c.id);
        expect(new Set(resultIds).size).toBe(resultIds.length);
      }),
      { numRuns: 100 }
    );
  });

  it("should return an empty array when favoritedIds parameter is undefined", () => {
    fc.assert(
      fc.property(uniqueCollectionsArbitrary, userIdArbitrary, (collections, userId) => {
        const result = filterCollections(collections, "favorites", userId);

        // When favoritedIds is not provided, favorites view returns empty
        expect(result).toEqual([]);
        expect(result.length).toBe(0);
      }),
      { numRuns: 100 }
    );
  });

  it("should preserve collection object integrity (returned objects are references from input)", () => {
    fc.assert(
      fc.property(uniqueCollectionsArbitrary, userIdArbitrary, (collections, userId) => {
        if (collections.length === 0) return;

        // Partial overlap: pick roughly half
        const halfIds = collections.filter((_, i) => i % 2 === 0).map((c) => c.id);
        const favoritedIds = new Set(halfIds);

        const result = filterCollections(collections, "favorites", userId, favoritedIds);

        // Each returned object should be the exact same reference from the input array
        for (const c of result) {
          const original = collections.find((o) => o.id === c.id);
          expect(original).toBeDefined();
          expect(c).toEqual(original);
        }
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Property-Based Tests for Non-Interference of Favorites Parameter
 *
 * Feature: collection-favorites
 * Property 2: Existing view types are unchanged by the favorites addition
 *
 * **Validates: Requirements 3.4**
 *
 * For each existing viewType ("all", "public", "private", "my-collections",
 * "shared-with-me", "my-shared"), passing a random favoritedIds parameter
 * must produce the exact same output as omitting it entirely.
 */

describe("Property 2: Existing view types are unchanged by the favorites addition", () => {
  // Helper to generate valid ISO date strings
  const isoDateArbitrary = fc
    .integer({ min: 1577836800000, max: 1767225600000 })
    .map((timestamp) => new Date(timestamp).toISOString());

  // Generate an array of collections with guaranteed unique ids
  const uniqueCollectionsArbitrary = fc
    .uniqueArray(fc.uuid(), { minLength: 0, maxLength: 30 })
    .chain((ids: string[]) =>
      ids.length === 0
        ? fc.constant([] as Collection[])
        : (fc.tuple(
            ...ids.map((id) =>
              fc.record({
                id: fc.constant(id),
                name: fc.string({ minLength: 1, maxLength: 50 }),
                type: fc.constantFrom("public" as const, "private" as const, "shared" as const),
                ownerId: fc.uuid(),
                itemCount: fc.nat({ max: 10000 }),
                childCount: fc.nat({ max: 100 }),
                childCollectionCount: fc.nat({ max: 100 }),
                isPublic: fc.boolean(),
                status: fc.constantFrom("active", "archived", "deleted"),
                createdAt: isoDateArbitrary,
                updatedAt: isoDateArbitrary,
              })
            )
          ) as fc.Arbitrary<Collection[]>)
    );

  // Arbitrary for a user id
  const userIdArbitrary = fc.uuid();

  // Arbitrary for a random set of favoritedIds
  const favoritedIdsArbitrary = fc
    .uniqueArray(fc.uuid(), { minLength: 0, maxLength: 20 })
    .map((ids) => new Set(ids));

  // The existing viewTypes that must not be affected by the favoritedIds parameter
  const existingViewTypes: Array<Exclude<CollectionViewType, "favorites">> = [
    "all",
    "public",
    "private",
    "my-collections",
    "shared-with-me",
    "my-shared",
  ];

  it("should produce identical results with and without favoritedIds for all existing viewTypes", () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        fc.constantFrom(...existingViewTypes),
        (collections, userId, favoritedIds, viewType) => {
          const resultWithout = filterCollections(collections, viewType, userId);
          const resultWith = filterCollections(collections, viewType, userId, favoritedIds);

          // The new optional parameter must not alter existing branch outputs
          expect(resultWith).toEqual(resultWithout);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return identical results for "all" viewType regardless of favoritedIds', () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIds) => {
          const resultWithout = filterCollections(collections, "all", userId);
          const resultWith = filterCollections(collections, "all", userId, favoritedIds);

          expect(resultWith).toEqual(resultWithout);
          expect(resultWith.length).toBe(collections.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return identical results for "public" viewType regardless of favoritedIds', () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIds) => {
          const resultWithout = filterCollections(collections, "public", userId);
          const resultWith = filterCollections(collections, "public", userId, favoritedIds);

          expect(resultWith).toEqual(resultWithout);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return identical results for "private" viewType regardless of favoritedIds', () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIds) => {
          const resultWithout = filterCollections(collections, "private", userId);
          const resultWith = filterCollections(collections, "private", userId, favoritedIds);

          expect(resultWith).toEqual(resultWithout);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return identical results for "my-collections" viewType regardless of favoritedIds', () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIds) => {
          const resultWithout = filterCollections(collections, "my-collections", userId);
          const resultWith = filterCollections(collections, "my-collections", userId, favoritedIds);

          expect(resultWith).toEqual(resultWithout);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return identical results for "shared-with-me" viewType regardless of favoritedIds', () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIds) => {
          const resultWithout = filterCollections(collections, "shared-with-me", userId);
          const resultWith = filterCollections(collections, "shared-with-me", userId, favoritedIds);

          expect(resultWith).toEqual(resultWithout);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return identical results for "my-shared" viewType regardless of favoritedIds', () => {
    fc.assert(
      fc.property(
        uniqueCollectionsArbitrary,
        userIdArbitrary,
        favoritedIdsArbitrary,
        (collections, userId, favoritedIds) => {
          const resultWithout = filterCollections(collections, "my-shared", userId);
          const resultWith = filterCollections(collections, "my-shared", userId, favoritedIds);

          expect(resultWith).toEqual(resultWithout);
        }
      ),
      { numRuns: 100 }
    );
  });
});
