import { describe, it, expect, beforeEach } from "vitest";
import { QueryClient } from "@tanstack/react-query";

// Mock the error modal hook used by useCollections — never called by the helper we test.
import { vi } from "vitest";

vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({ showError: vi.fn() }),
}));

import {
  patchCollectionInCache,
  type Collection,
  type PaginatedCollectionsResponse,
  type CollectionsResponse,
  type CollectionResponse,
  type CollectionAncestorsResponse,
} from "./useCollections";
import { QUERY_KEYS } from "../queryKeys";

// Minimal factory — covers the subset of fields the patcher reads/writes.
const makeCollection = (id: string, overrides: Partial<Collection> = {}): Collection => ({
  id,
  name: `Collection ${id}`,
  type: "private",
  ownerId: "user-1",
  itemCount: 0,
  childCount: 0,
  childCollectionCount: 0,
  isPublic: false,
  status: "active",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  thumbnailUrl: "https://cdn/old.png?v=2024-01-01",
  thumbnailType: "upload",
  ...overrides,
});

const makePaginated = (data: Collection[]): PaginatedCollectionsResponse => ({
  success: true,
  data,
  pagination: {
    page: 1,
    pageSize: 50,
    totalResults: data.length,
    totalPages: 1,
    hasNextPage: false,
    hasPrevPage: false,
  },
  meta: { timestamp: "", version: "v1", request_id: "req" },
});

const makeShared = (data: Collection[]): CollectionsResponse => ({
  success: true,
  data,
  pagination: {
    has_next_page: false,
    has_prev_page: false,
    limit: 50,
  },
  meta: { timestamp: "", version: "v1", request_id: "req" },
});

const makeDetail = (collection: Collection): CollectionResponse => ({
  success: true,
  data: collection,
  meta: { timestamp: "", version: "v1", request_id: "req" },
});

describe("patchCollectionInCache", () => {
  let queryClient: QueryClient;
  const targetId = "col-1";

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it("patches the paginated list cache", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.list({ page: 1 }),
      makePaginated([makeCollection(targetId), makeCollection("col-2", { name: "Other" })])
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
      thumbnailType: "upload",
    });

    const updated = queryClient.getQueryData<PaginatedCollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.list({ page: 1 })
    );
    expect(updated?.data[0].thumbnailUrl).toBe("https://cdn/new.png?v=2");
    expect(updated?.data[1].thumbnailUrl).toBe("https://cdn/old.png?v=2024-01-01");
  });

  it("patches the allCollections cache", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.allCollections(),
      makePaginated([makeCollection(targetId)])
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const updated = queryClient.getQueryData<PaginatedCollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.allCollections()
    );
    expect(updated?.data[0].thumbnailUrl).toBe("https://cdn/new.png?v=2");
  });

  it("patches the sharedWithMe cache (regression: sibling of lists())", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.sharedWithMe(),
      makeShared([makeCollection(targetId, { sharedWithMe: true })])
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const updated = queryClient.getQueryData<CollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.sharedWithMe()
    );
    expect(updated?.data[0].thumbnailUrl).toBe("https://cdn/new.png?v=2");
  });

  it("patches the sharedByMe cache (regression: sibling of lists())", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.sharedByMe(),
      makeShared([makeCollection(targetId)])
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const updated = queryClient.getQueryData<CollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.sharedByMe()
    );
    expect(updated?.data[0].thumbnailUrl).toBe("https://cdn/new.png?v=2");
  });

  it("patches the children(parentId) cache", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.children("parent-1"),
      makePaginated([makeCollection(targetId)])
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const updated = queryClient.getQueryData<PaginatedCollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.children("parent-1")
    );
    expect(updated?.data[0].thumbnailUrl).toBe("https://cdn/new.png?v=2");
  });

  it("patches the single-detail cache", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.detail(targetId),
      makeDetail(makeCollection(targetId))
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const updated = queryClient.getQueryData<CollectionResponse>(
      QUERY_KEYS.COLLECTIONS.detail(targetId)
    );
    expect(updated?.data.thumbnailUrl).toBe("https://cdn/new.png?v=2");
  });

  it("leaves ancestors cache intact even though it shares a prefix with details()", () => {
    // Ancestors is nested under details() in the key tree. The patcher's
    // prefix match will see this cache, so we rely on the id-match short-circuit
    // to avoid corrupting it. This regression test pins that behavior.
    const ancestorsResponse: CollectionAncestorsResponse = {
      success: true,
      data: [
        { id: "ancestor-1", name: "Root" },
        { id: "ancestor-2", name: "Parent" },
      ],
    };
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.ancestors("some-other-collection"),
      ancestorsResponse
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const after = queryClient.getQueryData<CollectionAncestorsResponse>(
      QUERY_KEYS.COLLECTIONS.ancestors("some-other-collection")
    );
    // Unchanged — no ancestor has id === targetId.
    expect(after).toBe(ancestorsResponse);
    expect(after?.data).toEqual(ancestorsResponse.data);
  });

  it("doesn't corrupt neighboring entries in a patched list", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.list({ page: 1 }),
      makePaginated([makeCollection("col-0"), makeCollection(targetId), makeCollection("col-2")])
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
    });

    const updated = queryClient.getQueryData<PaginatedCollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.list({ page: 1 })
    );
    expect(updated?.data[0].id).toBe("col-0");
    expect(updated?.data[0].thumbnailUrl).toBe("https://cdn/old.png?v=2024-01-01");
    expect(updated?.data[1].id).toBe(targetId);
    expect(updated?.data[1].thumbnailUrl).toBe("https://cdn/new.png?v=2");
    expect(updated?.data[2].id).toBe("col-2");
    expect(updated?.data[2].thumbnailUrl).toBe("https://cdn/old.png?v=2024-01-01");
  });

  it("patches multiple caches in a single call", () => {
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.list({ page: 1 }),
      makePaginated([makeCollection(targetId)])
    );
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.sharedWithMe(),
      makeShared([makeCollection(targetId)])
    );
    queryClient.setQueryData(
      QUERY_KEYS.COLLECTIONS.detail(targetId),
      makeDetail(makeCollection(targetId))
    );

    patchCollectionInCache(queryClient, targetId, {
      thumbnailUrl: "https://cdn/new.png?v=2",
      updatedAt: "2024-12-01T00:00:00Z",
    });

    const list = queryClient.getQueryData<PaginatedCollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.list({ page: 1 })
    );
    const shared = queryClient.getQueryData<CollectionsResponse>(
      QUERY_KEYS.COLLECTIONS.sharedWithMe()
    );
    const detail = queryClient.getQueryData<CollectionResponse>(
      QUERY_KEYS.COLLECTIONS.detail(targetId)
    );

    for (const source of [list?.data[0], shared?.data[0], detail?.data]) {
      expect(source?.thumbnailUrl).toBe("https://cdn/new.png?v=2");
      expect(source?.updatedAt).toBe("2024-12-01T00:00:00Z");
    }
  });
});
