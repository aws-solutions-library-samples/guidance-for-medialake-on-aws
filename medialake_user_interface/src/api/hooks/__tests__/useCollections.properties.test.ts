/**
 * Property-based tests for useGetCollections hook.
 *
 * Feature: collections-opensearch-listing
 * Property 7: Hook query parameter construction and cache key uniqueness
 *
 * Validates: Requirements 8.2, 8.4
 */

import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { QUERY_KEYS } from "@/api/queryKeys";

// ---------------------------------------------------------------------------
// URL builder — mirrors the logic in useGetCollections queryFn
// ---------------------------------------------------------------------------

interface UseGetCollectionsParams {
  page?: number;
  pageSize?: number;
  sort?: string;
  sortDirection?: "asc" | "desc";
  search?: string;
  filterOwnerId?: string;
  includeChildren?: boolean;
  groupIds?: string;
}

function buildCollectionsUrl(params: UseGetCollectionsParams): string {
  const urlParams = new URLSearchParams();
  if (params.page !== undefined) urlParams.append("page", String(params.page));
  if (params.pageSize !== undefined) urlParams.append("pageSize", String(params.pageSize));
  if (params.sort !== undefined) urlParams.append("sort", params.sort);
  if (params.sortDirection !== undefined) urlParams.append("sortDirection", params.sortDirection);
  if (params.search) urlParams.append("filter[search]", params.search);
  if (params.filterOwnerId) urlParams.append("filter[ownerId]", params.filterOwnerId);
  if (params.includeChildren !== undefined)
    urlParams.append("includeChildren", String(params.includeChildren));
  if (params.groupIds !== undefined) urlParams.append("groupIds", params.groupIds);
  return `/collections?${urlParams}`;
}

function buildCacheKey(params: UseGetCollectionsParams): readonly unknown[] {
  return QUERY_KEYS.COLLECTIONS.list(params);
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const safeString = fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0);

const pageArb = fc.integer({ min: 1, max: 1000 });
const pageSizeArb = fc.integer({ min: 1, max: 500 });
const sortArb = fc.constantFrom("name", "createdAt", "updatedAt");
const sortDirectionArb = fc.constantFrom("asc" as const, "desc" as const);

const paramsArb = fc.record(
  {
    page: pageArb,
    pageSize: pageSizeArb,
    sort: sortArb,
    sortDirection: sortDirectionArb,
    search: safeString,
    filterOwnerId: safeString,
    includeChildren: fc.boolean(),
    groupIds: safeString,
  },
  { requiredKeys: [] } // all fields optional
);

// ---------------------------------------------------------------------------
// Property 7: Hook query parameter construction and cache key uniqueness
// ---------------------------------------------------------------------------

describe("Feature: collections-opensearch-listing, Property 7: Hook query parameter construction and cache key uniqueness", () => {
  /**
   * Test 1: URL construction — for any combination of params, the URL should
   * contain the correct query parameters.
   */
  it("URL contains correct query parameters for any param combination", () => {
    fc.assert(
      fc.property(paramsArb, (params) => {
        const url = buildCollectionsUrl(params);

        // page
        if (params.page !== undefined) {
          expect(url).toContain(`page=${params.page}`);
        }

        // pageSize
        if (params.pageSize !== undefined) {
          expect(url).toContain(`pageSize=${params.pageSize}`);
        }

        // sort
        if (params.sort !== undefined) {
          expect(url).toContain(`sort=${params.sort}`);
        }

        // sortDirection
        if (params.sortDirection !== undefined) {
          expect(url).toContain(`sortDirection=${params.sortDirection}`);
        }

        // Parse the query string for value comparisons (handles special chars)
        const qs = new URLSearchParams(url.split("?")[1]);

        // search → filter[search]=<value>
        if (params.search) {
          expect(qs.get("filter[search]")).toBe(params.search);
        }

        // filterOwnerId → filter[ownerId]=<value>
        if (params.filterOwnerId) {
          expect(qs.get("filter[ownerId]")).toBe(params.filterOwnerId);
        }

        // includeChildren
        if (params.includeChildren !== undefined) {
          expect(url).toContain(`includeChildren=${params.includeChildren}`);
        }

        // groupIds
        if (params.groupIds !== undefined) {
          expect(qs.get("groupIds")).toBe(params.groupIds);
        }

        // URL must NOT contain limit= (old parameter removed)
        expect(url).not.toContain("limit=");
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Test 2: Cache key uniqueness — two different param combinations should
   * produce different cache keys.
   */
  it("different param combinations produce different cache keys", () => {
    fc.assert(
      fc.property(paramsArb, paramsArb, fc.context(), (params1, params2, ctx) => {
        // Only test cases where params actually differ
        const p1Str = JSON.stringify(params1);
        const p2Str = JSON.stringify(params2);
        fc.pre(p1Str !== p2Str);

        const key1 = buildCacheKey(params1);
        const key2 = buildCacheKey(params2);

        // Cache keys must differ when params differ
        expect(JSON.stringify(key1)).not.toEqual(JSON.stringify(key2));
      }),
      { numRuns: 100 }
    );
  });
});
