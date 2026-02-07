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
