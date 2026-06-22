/**
 * Unit tests for `useRecentCollections` hook.
 *
 * Validates: Requirements 12.1, 12.4
 *
 * Coverage:
 *   1. Pagination advances via nextCursor (fetchNextPage fetches the next page)
 *   2. Query key stability across renders (same pageSize -> same query key)
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import React from "react";

import { server } from "../../../mocks/server";
import { QUERY_KEYS } from "../../queryKeys";

// Mock useErrorModal to prevent side effects
vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError: vi.fn() }),
}));

import { useRecentCollections, type RecentCollectionsResponse } from "../useCollections";

/**
 * A syntactically valid, non-expired JWT so the apiClient's auth interceptor
 * does not throw "No authentication token available".
 */
const FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig";

/**
 * Factory for mock recent-collections API responses.
 */
function makeRecentResponse(
  collections: Array<{ id: string; name: string }>,
  nextCursor: string | null = null
): RecentCollectionsResponse {
  return {
    success: true,
    data: collections.map((c) => ({
      id: c.id,
      name: c.name,
      type: "private" as const,
      ownerId: "user-1",
      itemCount: 0,
      childCount: 0,
      childCollectionCount: 0,
      isPublic: false,
      status: "ACTIVE",
      userRole: "owner",
      createdAt: "2025-01-01T00:00:00Z",
      updatedAt: "2025-01-01T00:00:00Z",
    })),
    pagination: {
      pageSize: collections.length,
      nextCursor,
      hasNextPage: nextCursor !== null,
    },
    meta: {
      timestamp: new Date().toISOString(),
      version: "v1",
      request_id: "test-req",
    },
  };
}

/**
 * Fresh QueryClient per test — retries disabled for deterministic assertions.
 */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

/**
 * Wrapper component providing QueryClientProvider.
 */
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("useRecentCollections", () => {
  beforeEach(() => {
    // Seed the auth token so apiClient doesn't reject outbound requests
    localStorage.setItem("medialake-auth-token", FAKE_JWT);
  });

  describe("pagination advances via nextCursor", () => {
    it("fetches the first page and then advances to the next page using nextCursor", async () => {
      const page1Collections = [
        { id: "col-1", name: "Collection 1" },
        { id: "col-2", name: "Collection 2" },
      ];
      const page2Collections = [
        { id: "col-3", name: "Collection 3" },
        { id: "col-4", name: "Collection 4" },
      ];

      let requestCount = 0;

      server.use(
        http.get("*/collections/recent", ({ request }) => {
          const url = new URL(request.url);
          const cursor = url.searchParams.get("cursor");
          requestCount++;

          if (!cursor) {
            // First page — no cursor
            return HttpResponse.json(makeRecentResponse(page1Collections, "cursor-page-2"));
          } else if (cursor === "cursor-page-2") {
            // Second page
            return HttpResponse.json(makeRecentResponse(page2Collections, null));
          }

          return HttpResponse.json(makeRecentResponse([], null));
        })
      );

      const queryClient = makeQueryClient();

      const { result } = renderHook(() => useRecentCollections(2), {
        wrapper: createWrapper(queryClient),
      });

      // Wait for first page to load
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Verify first page data
      expect(result.current.data?.pages).toHaveLength(1);
      expect(result.current.data?.pages[0].data).toHaveLength(2);
      expect(result.current.data?.pages[0].data[0].id).toBe("col-1");
      expect(result.current.data?.pages[0].data[1].id).toBe("col-2");
      expect(result.current.data?.pages[0].pagination.nextCursor).toBe("cursor-page-2");
      expect(result.current.hasNextPage).toBe(true);

      // Fetch next page
      await act(async () => {
        await result.current.fetchNextPage();
      });

      // Wait for the second page to appear
      await waitFor(() => {
        expect(result.current.data?.pages).toHaveLength(2);
      });

      // Verify second page data
      expect(result.current.data?.pages[1].data).toHaveLength(2);
      expect(result.current.data?.pages[1].data[0].id).toBe("col-3");
      expect(result.current.data?.pages[1].data[1].id).toBe("col-4");
      expect(result.current.data?.pages[1].pagination.nextCursor).toBeNull();
      expect(result.current.hasNextPage).toBe(false);

      // Two requests total: first page + second page
      expect(requestCount).toBe(2);
    });

    it("passes the cursor as a query parameter to the API", async () => {
      const receivedCursors: Array<string | null> = [];

      server.use(
        http.get("*/collections/recent", ({ request }) => {
          const url = new URL(request.url);
          receivedCursors.push(url.searchParams.get("cursor"));

          const isFirstPage = receivedCursors.length === 1;
          return HttpResponse.json(
            makeRecentResponse(
              [{ id: `col-${receivedCursors.length}`, name: `C${receivedCursors.length}` }],
              isFirstPage ? "next-cursor-abc" : null
            )
          );
        })
      );

      const queryClient = makeQueryClient();
      const { result } = renderHook(() => useRecentCollections(5), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      // First request has no cursor
      expect(receivedCursors[0]).toBeNull();

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      // Wait for the second page to load
      await waitFor(() => {
        expect(receivedCursors).toHaveLength(2);
      });

      // Second request carries the cursor from the first response
      expect(receivedCursors[1]).toBe("next-cursor-abc");
    });
  });

  describe("query-key stability across renders", () => {
    it("generates the same query key for the same pageSize", () => {
      const key1 = QUERY_KEYS.COLLECTIONS.recent(5);
      const key2 = QUERY_KEYS.COLLECTIONS.recent(5);

      // Structurally equal
      expect(key1).toEqual(key2);
      // The factory must produce referentially stable content (same shape)
      expect(JSON.stringify(key1)).toBe(JSON.stringify(key2));
    });

    it("generates different query keys for different pageSizes", () => {
      const key5 = QUERY_KEYS.COLLECTIONS.recent(5);
      const key10 = QUERY_KEYS.COLLECTIONS.recent(10);

      expect(JSON.stringify(key5)).not.toBe(JSON.stringify(key10));
    });

    it("does not refetch when the hook re-renders with the same pageSize", async () => {
      let fetchCount = 0;

      server.use(
        http.get("*/collections/recent", () => {
          fetchCount++;
          return HttpResponse.json(makeRecentResponse([{ id: "col-1", name: "C1" }], null));
        })
      );

      const queryClient = makeQueryClient();

      const { result, rerender } = renderHook(
        ({ pageSize }: { pageSize: number }) => useRecentCollections(pageSize),
        {
          wrapper: createWrapper(queryClient),
          initialProps: { pageSize: 5 },
        }
      );

      // Wait for the initial fetch
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(fetchCount).toBe(1);

      // Re-render with the same pageSize — should NOT trigger another fetch
      rerender({ pageSize: 5 });

      // Give React Query a tick to confirm no re-fetch
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(fetchCount).toBe(1);
    });
  });
});
