import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import axios from "axios";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";

/**
 * Extract a human-readable error message from an API failure.
 *
 * Backend error envelope is `{"statusCode": <int>, "message": "..."}` (AWS Powertools).
 * Falls back through common shapes so we surface something useful in the UI instead of
 * a generic "Failed to ..." string that hides 4xx permission/validation reasons.
 */
const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { message?: string; error?: string; detail?: string }
      | undefined;
    const message = data?.message || data?.error || data?.detail;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

/**
 * Apply a partial patch to a collection across every cached query that contains it:
 * all paginated list queries (including `allCollections` which nests under `lists()`),
 * any cached `children(parentId)` queries, and the single `detail(id)` cache.
 * Used by mutations to reflect server changes immediately without waiting for a refetch.
 *
 * The backend appends a `?v=<updatedAt>` cache-bust token to every
 * `thumbnailUrl`, so the URL naturally changes after an upload even though the
 * S3 key is stable — no extra client-side busting needed here.
 */
export const patchCollectionInCache = (
  queryClient: ReturnType<typeof useQueryClient>,
  collectionId: string,
  patch: Partial<Collection>
) => {
  const effectivePatch: Partial<Collection> = { ...patch };

  // Helper that maps an array-shaped response to a new object with the target
  // collection's fields merged. Guards on the array element's own `id` being
  // a string so we don't corrupt neighboring cache types (e.g. ancestors,
  // which share a prefix in the key tree) — if the shape doesn't match, we
  // leave the cache alone.
  const applyToArrayResponse = <T extends { data: unknown }>(old: T | undefined): T | undefined => {
    if (!old || !Array.isArray((old as { data: unknown }).data)) return old;
    const arr = (old as unknown as { data: Array<Record<string, unknown>> }).data;
    // Only touch the cache if at least one element actually matches — avoids
    // pointlessly cloning large lists.
    const idx = arr.findIndex((c) => typeof c?.id === "string" && c.id === collectionId);
    if (idx === -1) return old;
    const next = arr.map((c) =>
      typeof c?.id === "string" && c.id === collectionId ? { ...c, ...effectivePatch } : c
    );
    return { ...(old as object), data: next } as T;
  };

  // Paginated lists + allCollections (nested under lists())
  queryClient.setQueriesData<PaginatedCollectionsResponse>(
    { queryKey: QUERY_KEYS.COLLECTIONS.lists() },
    applyToArrayResponse
  );

  // Shared tabs — siblings of `lists()`, not covered by the prefix match above.
  queryClient.setQueriesData<CollectionsResponse>(
    { queryKey: QUERY_KEYS.COLLECTIONS.sharedWithMe() },
    applyToArrayResponse
  );
  queryClient.setQueriesData<CollectionsResponse>(
    { queryKey: QUERY_KEYS.COLLECTIONS.sharedByMe() },
    applyToArrayResponse
  );

  // Every children(parentId) cache, nested under details().
  queryClient.setQueriesData<PaginatedCollectionsResponse>(
    { queryKey: QUERY_KEYS.COLLECTIONS.details() },
    applyToArrayResponse
  );

  // Single-detail cache for the updated collection.
  queryClient.setQueryData<CollectionResponse>(
    QUERY_KEYS.COLLECTIONS.detail(collectionId),
    (old) => {
      if (!old) return old;
      return { ...old, data: { ...old.data, ...effectivePatch } };
    }
  );
};

// Thumbnail types matching the backend enum
export type ThumbnailType = "icon" | "upload" | "asset" | "frame";

// Collection types following the backend API schema
export interface Collection {
  id: string;
  name: string;
  description?: string;
  type: "public" | "private" | "shared";
  parentId?: string;
  collectionTypeId?: string;
  ownerId: string;
  ownerName?: string;
  itemCount: number;
  childCount: number;
  childCollectionCount: number;
  isPublic: boolean;
  status: string;
  userRole?: string;
  createdAt: string;
  updatedAt: string;
  // Thumbnail fields
  thumbnailType?: ThumbnailType;
  thumbnailValue?: string; // icon name or source asset ID
  thumbnailUrl?: string; // resolved CloudFront URL for uploaded/asset/frame thumbnails
  // Sharing metadata
  isShared?: boolean;
  shareCount?: number;
  sharedWithMe?: boolean;
  myRole?: string;
  sharedAt?: string;
  sharedWith?: Array<{
    targetId: string;
    targetType: string;
    role: string;
    grantedAt: string;
  }>;
  ancestors?: Array<{
    id: string;
    name: string;
    parentId?: string;
  }>;
  customMetadata?: Record<string, string>;
  // Free-form tag array backed by the OpenSearch `tags` keyword field.
  // Backend has always populated this; it's surfaced on the UI starting with the
  // collections redesign so cards, detail pages, and filters can use it.
  tags?: string[];
}

export interface CollectionType {
  id: string;
  name: string;
  description?: string;
  color: string;
  icon: string;
  isActive: boolean;
  isSystem: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CreateCollectionTypeRequest {
  name: string;
  description?: string;
  color: string;
  icon: string;
  isActive?: boolean;
}

export interface UpdateCollectionTypeRequest {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
  isActive?: boolean;
}

export interface MigrateCollectionTypeRequest {
  targetTypeId: string;
}

export interface CreateCollectionRequest {
  name: string;
  description?: string;
  parentId?: string;
  isPublic?: boolean;
  type?: string;
  collectionTypeId?: string;
  metadata?: Record<string, string>;
}

export interface UpdateCollectionRequest {
  name?: string;
  description?: string;
  parentId?: string;
  isPublic?: boolean;
  collectionTypeId?: string;
  metadata?: Record<string, string>;
}

export interface ShareCollectionRequest {
  targetUserId: string;
  accessLevel: "VIEWER" | "EDITOR" | "ADMIN";
  message?: string;
}

export interface AddItemToCollectionRequest {
  assetId: string;
  clipBoundary?: {
    startTime?: string;
    endTime?: string;
  };
  addAllClips?: boolean;
  // Legacy fields for backward compatibility
  type?: "asset" | "workflow" | "collection";
  id?: string;
  sortOrder?: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata?: Record<string, any>;
}

export interface CollectionShare {
  id?: string;
  collectionId?: string;
  userId?: string;
  targetId?: string;
  targetType?: string;
  groupId?: string;
  role: string;
  expiresAt?: string;
  createdAt?: string;
  grantedAt?: string;
  grantedBy?: string;
  sharedBy?: string;
  message?: string;
}

export interface CollectionsResponse {
  success: boolean;
  data: Collection[];
  pagination: {
    has_next_page: boolean;
    has_prev_page: boolean;
    limit: number;
    next_cursor?: string;
    prev_cursor?: string;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface PaginatedCollectionsResponse {
  success: boolean;
  data: Collection[];
  pagination: {
    page: number;
    pageSize: number;
    totalResults: number;
    totalPages: number;
    hasNextPage: boolean;
    hasPrevPage: boolean;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface UseGetCollectionsParams {
  page?: number;
  pageSize?: number;
  sort?: string;
  sortDirection?: "asc" | "desc";
  search?: string;
  filterOwnerId?: string;
  includeChildren?: boolean;
  groupIds?: string;
  enabled?: boolean;
  metadataFilters?: Record<string, string>;
  // Filter by tag values (OR semantics). Each value becomes a repeated
  // `filter[tag]=<value>` query param — matches the backend's multi-value parser.
  tagFilters?: string[];
  // Filter by visibility facet. Values: "public" | "shared" | "private".
  visibilityFilters?: string[];
  // Bucketed "updated within last N" filter. Values: "24h" | "7d" | "30d".
  updatedWithin?: string;
}

export interface CollectionResponse {
  success: boolean;
  data: Collection;
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface CollectionTypesResponse {
  success: boolean;
  data: CollectionType[];
  pagination: {
    has_next_page: boolean;
    has_prev_page: boolean;
    limit: number;
    next_cursor?: string;
    prev_cursor?: string;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface CollectionTypeResponse {
  success: boolean;
  data: CollectionType;
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface MigrateCollectionTypeResponse {
  success: boolean;
  data: {
    migratedCount: number;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface CollectionSharesResponse {
  success: boolean;
  data: CollectionShare[];
  pagination: {
    has_next_page: boolean;
    has_prev_page: boolean;
    limit: number;
    next_cursor?: string;
    prev_cursor?: string;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

export interface CollectionAssetsResponse {
  success: boolean;
  data: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    results: any[]; // Using any[] to match search results format
    searchMetadata: {
      totalResults: number;
      page: number;
      pageSize: number;
    };
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

// Hook to get all collections for the current user (paginated, server-side)
export const useGetCollections = (params: UseGetCollectionsParams = {}) => {
  const { showError } = useErrorModal();
  const { enabled = true, ...queryParams } = params;

  return useQuery<PaginatedCollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.list(queryParams),
    placeholderData: keepPreviousData,
    enabled,
    queryFn: async ({ signal }) => {
      try {
        const urlParams = new URLSearchParams();
        if (params.page !== undefined) urlParams.append("page", String(params.page));
        if (params.pageSize !== undefined) urlParams.append("pageSize", String(params.pageSize));
        if (params.sort !== undefined) urlParams.append("sort", params.sort);
        if (params.sortDirection !== undefined)
          urlParams.append("sortDirection", params.sortDirection);
        if (params.search) urlParams.append("filter[search]", params.search);
        if (params.filterOwnerId) urlParams.append("filter[ownerId]", params.filterOwnerId);
        if (params.includeChildren !== undefined)
          urlParams.append("includeChildren", String(params.includeChildren));
        if (params.groupIds !== undefined) urlParams.append("groupIds", params.groupIds);
        if (params.metadataFilters) {
          for (const [key, value] of Object.entries(params.metadataFilters)) {
            urlParams.append(`filter[metadata.${key}]`, value);
          }
        }
        if (params.tagFilters && params.tagFilters.length > 0) {
          for (const tag of params.tagFilters) {
            urlParams.append("filter[tag]", tag);
          }
        }
        if (params.visibilityFilters && params.visibilityFilters.length > 0) {
          for (const v of params.visibilityFilters) {
            urlParams.append("filter[visibility]", v);
          }
        }
        if (params.updatedWithin) {
          urlParams.append("filter[updatedWithin]", params.updatedWithin);
        }

        const url = `${API_ENDPOINTS.COLLECTIONS.BASE}?${urlParams}`;

        const response = await apiClient.get<PaginatedCollectionsResponse>(url, { signal });
        return response.data;
      } catch (error) {
        logger.error("Fetch collections error:", error);
        showError("Failed to fetch collections");
        throw error;
      }
    },
  });
};

// Hook to get ALL collections (roots + children) for tree views, dropdowns, and modals.
// Pages through the backend until every collection is loaded so tree views are complete
// regardless of tenant size. The backend caps pageSize at 1000 and enforces
// (page - 1) * pageSize < 10000 (OpenSearch max_result_window), giving us a hard ceiling
// of 10,000 collections per call. If a tenant exceeds that, we surface a warning so the
// issue is visible in the console rather than silently truncating the tree.
const ALL_COLLECTIONS_PAGE_SIZE = 1000;
const ALL_COLLECTIONS_MAX_PAGES = 10; // 10 * 1000 = 10,000 (OpenSearch max_result_window)

export const useGetAllCollections = () => {
  const { showError } = useErrorModal();

  return useQuery<PaginatedCollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.allCollections(),
    queryFn: async ({ signal }) => {
      try {
        const aggregated: Collection[] = [];
        let page = 1;
        let lastResponse: PaginatedCollectionsResponse | undefined;

        while (page <= ALL_COLLECTIONS_MAX_PAGES) {
          const urlParams = new URLSearchParams();
          urlParams.append("page", String(page));
          urlParams.append("pageSize", String(ALL_COLLECTIONS_PAGE_SIZE));
          urlParams.append("includeChildren", "true");
          // Stable sort so paging across requests is deterministic
          urlParams.append("sort", "name");
          urlParams.append("sortDirection", "asc");

          const url = `${API_ENDPOINTS.COLLECTIONS.BASE}?${urlParams}`;
          const response = await apiClient.get<PaginatedCollectionsResponse>(url, { signal });
          lastResponse = response.data;

          if (lastResponse?.data?.length) {
            aggregated.push(...lastResponse.data);
          }

          if (!lastResponse?.pagination?.hasNextPage) {
            break;
          }
          page += 1;
        }

        if (!lastResponse) {
          throw new Error("useGetAllCollections: no response received");
        }

        const totalResults = lastResponse.pagination?.totalResults ?? aggregated.length;
        if (aggregated.length < totalResults) {
          console.warn(
            `useGetAllCollections: fetched ${aggregated.length} of ${totalResults} collections. ` +
              `OpenSearch max_result_window (${
                ALL_COLLECTIONS_MAX_PAGES * ALL_COLLECTIONS_PAGE_SIZE
              }) reached — ` +
              `tree views may be incomplete.`
          );
        }

        return {
          ...lastResponse,
          data: aggregated,
          pagination: {
            ...lastResponse.pagination,
            page: 1,
            pageSize: aggregated.length,
            totalPages: 1,
            hasNextPage: false,
            hasPrevPage: false,
          },
        };
      } catch (error) {
        // Silently ignore aborted requests (expected during unmount / refetch)
        if (axios.isCancel(error) || (error as Error)?.name === "CanceledError") {
          throw error;
        }
        logger.error("Fetch all collections error:", error);
        showError("Failed to fetch collections");
        throw error;
      }
    },
  });
};

// Hook to get collections shared with the current user
export const useGetCollectionsSharedWithMe = () => {
  const { showError } = useErrorModal();

  return useQuery<CollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.sharedWithMe(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionsResponse>(
          API_ENDPOINTS.COLLECTIONS.SHARED_WITH_ME,
          { signal }
        );
        return response.data;
      } catch (error) {
        // Silently ignore canceled requests (expected during auth redirects/re-renders)
        if (axios.isCancel(error)) {
          throw error;
        }
        logger.error("Fetch collections shared with me error:", error);
        showError("Failed to fetch shared collections");
        throw error;
      }
    },
  });
};

// Hook to get collections shared by the current user
export const useGetCollectionsSharedByMe = () => {
  const { showError } = useErrorModal();

  return useQuery<CollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.sharedByMe(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionsResponse>(
          API_ENDPOINTS.COLLECTIONS.SHARED_BY_ME,
          { signal }
        );
        return response.data;
      } catch (error) {
        if (axios.isCancel(error)) {
          throw error;
        }
        logger.error("Fetch collections shared by me error:", error);
        showError("Failed to fetch collections you've shared");
        throw error;
      }
    },
  });
};

// Alias for backwards compatibility
export const useGetSharedCollections = useGetCollectionsSharedWithMe;

// Hook to get a single collection by ID
export const useGetCollection = (id: string, enabled = true) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.detail(id),
    enabled: enabled && !!id,
    placeholderData: keepPreviousData, // Keep previous collection visible during navigation
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionResponse>(
          API_ENDPOINTS.COLLECTIONS.GET(id),
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch collection error:", error);
        showError("Failed to fetch collection");
        throw error;
      }
    },
  });
};

// Hook to get child collections for a parent collection
export const useGetChildCollections = (parentId: string, enabled = true) => {
  const { showError } = useErrorModal();

  return useQuery<PaginatedCollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.children(parentId),
    enabled: enabled && !!parentId,
    placeholderData: keepPreviousData, // Keep previous children visible during navigation
    queryFn: async ({ signal }) => {
      try {
        const params = new URLSearchParams();
        params.append("filter[parentId]", parentId);

        const response = await apiClient.get<PaginatedCollectionsResponse>(
          `${API_ENDPOINTS.COLLECTIONS.BASE}?${params}`,
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch child collections error:", error);
        showError("Failed to fetch child collections");
        throw error;
      }
    },
  });
};

// Hook to create a new collection
export const useCreateCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<CollectionResponse, Error, CreateCollectionRequest>({
    mutationFn: async (data) => {
      try {
        const response = await apiClient.post<CollectionResponse>(
          API_ENDPOINTS.COLLECTIONS.BASE,
          data
        );
        return response.data;
      } catch (error) {
        logger.error("Create collection error:", error);
        showError("Failed to create collection");
        throw error;
      }
    },
    onSuccess: (result, variables) => {
      // Backend write-through ensures OpenSearch is immediately consistent.
      // Invalidate all relevant caches so React Query refetches sorted data.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.COLLECTIONS.lists() });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.allCollections(),
      });

      if (variables.parentId) {
        queryClient.invalidateQueries({
          queryKey: QUERY_KEYS.COLLECTIONS.children(variables.parentId),
        });
        queryClient.invalidateQueries({
          queryKey: QUERY_KEYS.COLLECTIONS.detail(variables.parentId),
        });
      }
    },
  });
};

// Hook to update a collection
export const useUpdateCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<CollectionResponse, Error, { id: string; data: UpdateCollectionRequest }>({
    mutationFn: async ({ id, data }) => {
      try {
        const response = await apiClient.patch<CollectionResponse>(
          API_ENDPOINTS.COLLECTIONS.UPDATE(id),
          data
        );
        return response.data;
      } catch (error) {
        logger.error("Update collection error:", error);
        const message = getApiErrorMessage(error, "Failed to update collection");
        showError(message);
        throw new Error(message);
      }
    },
    onSuccess: (result, { id }) => {
      // Backend write-through ensures OpenSearch is immediately consistent.
      // Invalidate all relevant caches so React Query refetches fresh data.
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.allCollections(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(id),
      });
    },
  });
};

// Hook to delete a collection
export const useDeleteCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      try {
        await apiClient.delete(API_ENDPOINTS.COLLECTIONS.DELETE(id));
      } catch (error) {
        logger.error("Delete collection error:", error);
        showError("Failed to delete collection");
        throw error;
      }
    },
    onSuccess: (_, deletedId) => {
      // Find the deleted collection's parentId from the cache (if it's a sub-collection)
      let parentId: string | undefined;
      const allCollData = queryClient.getQueryData<PaginatedCollectionsResponse>(
        QUERY_KEYS.COLLECTIONS.allCollections()
      );
      if (allCollData) {
        const deleted = allCollData.data.find((c) => c.id === deletedId);
        parentId = deleted?.parentId;
      }

      // Fall back to the single-collection detail cache if allCollections didn't have it
      if (!parentId) {
        const detailData = queryClient.getQueryData<CollectionResponse>(
          QUERY_KEYS.COLLECTIONS.detail(deletedId)
        );
        parentId = detailData?.data?.parentId;
      }

      // Optimistically remove from all list caches
      queryClient.setQueriesData<PaginatedCollectionsResponse>(
        { queryKey: QUERY_KEYS.COLLECTIONS.lists() },
        (old) => {
          if (!old) return old;
          const filtered = old.data.filter((c) => c.id !== deletedId);
          return {
            ...old,
            data: filtered,
            pagination: {
              ...old.pagination,
              totalResults: Math.max(0, old.pagination.totalResults - 1),
            },
          };
        }
      );

      // If it was a sub-collection, also remove from parent's children cache
      if (parentId) {
        queryClient.setQueryData<PaginatedCollectionsResponse>(
          QUERY_KEYS.COLLECTIONS.children(parentId),
          (old) => {
            if (!old) return old;
            const filtered = old.data.filter((c) => c.id !== deletedId);
            return {
              ...old,
              data: filtered,
              pagination: {
                ...old.pagination,
                totalResults: Math.max(0, old.pagination.totalResults - 1),
              },
            };
          }
        );

        // Decrement parent's childCollectionCount
        queryClient.setQueryData<CollectionResponse>(
          QUERY_KEYS.COLLECTIONS.detail(parentId),
          (old) => {
            if (!old) return old;
            return {
              ...old,
              data: {
                ...old.data,
                childCollectionCount: Math.max(0, (old.data.childCollectionCount || 0) - 1),
              },
            };
          }
        );
      }

      // Invalidate to get fresh data
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shared(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.allCollections(),
      });
    },
  });
};

// Hook to delete item from collection
export const useDeleteItemFromCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<void, Error, { collectionId: string; itemId: string }>({
    mutationFn: async ({ collectionId, itemId }) => {
      try {
        // URL-encode the itemId to handle special characters like #
        const encodedItemId = encodeURIComponent(itemId);
        await apiClient.delete(`/collections/${collectionId}/items/${encodedItemId}`);
      } catch (error) {
        logger.error("Delete item from collection error:", error);
        showError("Failed to remove item from collection");
        throw error;
      }
    },
    onSuccess: (_, variables) => {
      // Invalidate the specific collection's assets query
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.assets(variables.collectionId),
      });
      // Also invalidate the collection details to update item count
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(variables.collectionId),
      });
    },
  });
};

// Hook to share a collection
export const useShareCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<void, Error, { id: string; data: ShareCollectionRequest }>({
    mutationFn: async ({ id, data }) => {
      try {
        await apiClient.post(API_ENDPOINTS.COLLECTIONS.SHARE(id), data);
      } catch (error) {
        logger.error("Share collection error:", error);
        showError("Failed to share collection");
        throw error;
      }
    },
    onSuccess: (data, { id }) => {
      // Invalidate collection shares
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shares(id),
      });
    },
  });
};

// Hook to unshare a collection
export const useUnshareCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<void, Error, { id: string; userId: string }>({
    mutationFn: async ({ id, userId }) => {
      try {
        await apiClient.delete(API_ENDPOINTS.COLLECTIONS.UNSHARE(id, userId));
      } catch (error) {
        logger.error("Unshare collection error:", error);
        showError("Failed to unshare collection");
        throw error;
      }
    },
    onSuccess: (data, { id }) => {
      // Invalidate collection shares
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shares(id),
      });
    },
  });
};

// Hook to add item to collection
export const useAddItemToCollection = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<void, Error, { collectionId: string; data: AddItemToCollectionRequest }>({
    mutationFn: async ({ collectionId, data }) => {
      try {
        await apiClient.post(API_ENDPOINTS.COLLECTIONS.ITEMS(collectionId), data);
      } catch (error) {
        logger.error("Add item to collection error:", error);
        showError("Failed to add item to collection");
        throw error;
      }
    },
    onSuccess: (data, { collectionId }) => {
      // Optimistically increment itemCount so the card updates immediately
      // without waiting for the refetch (which may still show the old count
      // due to OpenSearch eventual consistency).
      const detail = queryClient.getQueryData<CollectionResponse>(
        QUERY_KEYS.COLLECTIONS.detail(collectionId)
      );
      let currentCount = detail?.data?.itemCount;
      if (currentCount === undefined) {
        // Fall back to finding the count from any list cache
        const lists = queryClient.getQueriesData<PaginatedCollectionsResponse>({
          queryKey: QUERY_KEYS.COLLECTIONS.lists(),
        });
        for (const [, listData] of lists) {
          const match = listData?.data?.find((c) => c.id === collectionId);
          if (match) {
            currentCount = match.itemCount;
            break;
          }
        }
      }
      patchCollectionInCache(queryClient, collectionId, {
        itemCount: (currentCount ?? 0) + 1,
      });

      // Invalidate so the next natural refetch reconciles with the server.
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(collectionId),
      });
    },
  });
};

// Hook to get collection shares
export const useGetCollectionShares = (id: string, enabled = true) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionSharesResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.shares(id),
    enabled: enabled && !!id,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionSharesResponse>(
          API_ENDPOINTS.COLLECTIONS.SHARES(id),
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch collection shares error:", error);
        showError("Failed to fetch collection shares");
        throw error;
      }
    },
  });
};

// Hook to get collection assets for viewing
export const useGetCollectionAssets = (
  id: string,
  filters?: {
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortDirection?: "asc" | "desc";
  },
  enabled = true
) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionAssetsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.assets(id, filters),
    enabled: enabled && !!id,
    placeholderData: keepPreviousData, // Keep previous assets visible during navigation
    queryFn: async ({ signal }) => {
      try {
        const params = new URLSearchParams();
        if (filters) {
          Object.entries(filters).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              params.append(key, String(value));
            }
          });
        }

        const url = params.toString()
          ? `${API_ENDPOINTS.COLLECTIONS.ASSETS(id)}?${params}`
          : API_ENDPOINTS.COLLECTIONS.ASSETS(id);

        const response = await apiClient.get<CollectionAssetsResponse>(url, {
          signal,
        });
        return response.data;
      } catch (error) {
        logger.error("Fetch collection assets error:", error);
        showError("Failed to fetch collection assets");
        throw error;
      }
    },
  });
};

// Hook to get collection ancestors (breadcrumb trail)
export interface CollectionAncestor {
  id: string;
  name: string;
  parentId?: string;
}

export interface CollectionAncestorsResponse {
  success: boolean;
  data: CollectionAncestor[];
}

export const useGetCollectionAncestors = (id: string, enabled = true) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionAncestorsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.ancestors(id),
    enabled: enabled && !!id,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionAncestorsResponse>(
          API_ENDPOINTS.COLLECTIONS.ANCESTORS(id),
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch collection ancestors error:", error);
        showError("Failed to fetch collection ancestors");
        throw error;
      }
    },
  });
};

// =============================================================================
// Metadata Keys Hook
// =============================================================================

export interface MetadataKeysResponse {
  success: boolean;
  data: { keys: string[] };
  meta: { timestamp: string; version: string; request_id: string };
}

/**
 * Hook to fetch all distinct metadata key names for the filter dropdown.
 * Uses a 60-second staleTime to avoid redundant API calls.
 */
export const useGetMetadataKeys = () => {
  const { showError } = useErrorModal();

  return useQuery<MetadataKeysResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.metadataKeys(),
    staleTime: 60_000,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<MetadataKeysResponse>(
          API_ENDPOINTS.COLLECTIONS.METADATA_KEYS,
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch metadata keys error:", error);
        showError("Failed to fetch metadata keys");
        throw error;
      }
    },
  });
};

// =============================================================================
// Collection Types Hooks
// =============================================================================

/**
 * Hook to fetch all collection types
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const useGetCollectionTypes = (filters?: Record<string, any>) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionTypesResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTION_TYPES.list(filters),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionTypesResponse>(
          API_ENDPOINTS.COLLECTION_TYPES.BASE,
          { params: filters, signal }
        );
        return response.data;
      } catch (error) {
        // Silently ignore canceled requests (expected during auth redirects/re-renders)
        if (axios.isCancel(error)) {
          throw error;
        }
        logger.error("Fetch collection types error:", error);
        showError("Failed to fetch collection types");
        throw error;
      }
    },
  });
};

/**
 * Hook to fetch a single collection type by ID
 */
export const useGetCollectionType = (id: string, enabled = true) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionTypeResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTION_TYPES.detail(id),
    enabled: enabled && !!id,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionTypeResponse>(
          API_ENDPOINTS.COLLECTION_TYPES.GET(id),
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch collection type error:", error);
        showError("Failed to fetch collection type");
        throw error;
      }
    },
  });
};

/**
 * Hook to create a new collection type
 */
export const useCreateCollectionType = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async (data: CreateCollectionTypeRequest) => {
      try {
        const response = await apiClient.post<CollectionTypeResponse>(
          API_ENDPOINTS.COLLECTION_TYPES.BASE,
          data
        );
        return response.data;
      } catch (error) {
        logger.error("Create collection type error:", error);
        showError("Failed to create collection type");
        throw error;
      }
    },
    onSuccess: () => {
      // Invalidate and refetch collection types
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTION_TYPES.lists(),
      });
    },
  });
};

/**
 * Hook to update a collection type
 */
export const useUpdateCollectionType = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: UpdateCollectionTypeRequest }) => {
      try {
        const response = await apiClient.put<CollectionTypeResponse>(
          API_ENDPOINTS.COLLECTION_TYPES.UPDATE(id),
          data
        );
        return response.data;
      } catch (error) {
        logger.error("Update collection type error:", error);
        showError("Failed to update collection type");
        throw error;
      }
    },
    onSuccess: (_, variables) => {
      // Invalidate the specific type and lists
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTION_TYPES.detail(variables.id),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTION_TYPES.lists(),
      });
    },
  });
};

/**
 * Hook to delete a collection type
 */
export const useDeleteCollectionType = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async (id: string) => {
      try {
        await apiClient.delete(API_ENDPOINTS.COLLECTION_TYPES.DELETE(id));
      } catch (error) {
        logger.error("Delete collection type error:", error);
        showError("Failed to delete collection type");
        throw error;
      }
    },
    onSuccess: () => {
      // Invalidate collection types list
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTION_TYPES.lists(),
      });
    },
  });
};

/**
 * Hook to migrate collections from one type to another
 */
export const useMigrateCollectionType = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async ({
      sourceTypeId,
      targetTypeId,
    }: {
      sourceTypeId: string;
      targetTypeId: string;
    }) => {
      try {
        const response = await apiClient.post<MigrateCollectionTypeResponse>(
          API_ENDPOINTS.COLLECTION_TYPES.MIGRATE(sourceTypeId),
          { targetTypeId }
        );
        return response.data;
      } catch (error) {
        logger.error("Migrate collection type error:", error);
        showError("Failed to migrate collections");
        throw error;
      }
    },
    onSuccess: () => {
      // Invalidate collection types and collections
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTION_TYPES.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
    },
  });
};

// =============================================================================
// Collection Thumbnail Hooks
// =============================================================================

export type ThumbnailSource = "upload" | "asset" | "frame";

export interface SetCollectionThumbnailRequest {
  source: ThumbnailSource;
  data?: string; // Base64 image data for 'upload' or 'frame' source
  assetId?: string; // Asset ID for 'asset' source
}

export interface SetCollectionThumbnailResponse {
  success: boolean;
  data: {
    thumbnailType: ThumbnailType;
    thumbnailValue?: string;
    thumbnailUrl: string;
    /**
     * ISO-8601 timestamp. Bumps whenever the thumbnail is replaced so the
     * `?v=<token>` cache-bust query string in `thumbnailUrl` changes too.
     * Consumers that display `updatedAt` should patch it on success so the
     * meta row stays in sync with the new URL.
     */
    updatedAt?: string;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id: string;
  };
}

/**
 * Hook to set a collection thumbnail
 * Supports uploading an image, using an asset's thumbnail, or capturing a video frame
 */
export const useSetCollectionThumbnail = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<
    SetCollectionThumbnailResponse,
    Error,
    { collectionId: string; data: SetCollectionThumbnailRequest }
  >({
    mutationFn: async ({ collectionId, data }) => {
      try {
        const response = await apiClient.post<SetCollectionThumbnailResponse>(
          API_ENDPOINTS.COLLECTIONS.THUMBNAIL(collectionId),
          data
        );
        return response.data;
      } catch (error) {
        logger.error("Set collection thumbnail error:", error);
        const message = getApiErrorMessage(error, "Failed to set collection thumbnail");
        showError(message);
        throw new Error(message);
      }
    },
    onSuccess: (response, { collectionId }) => {
      // Optimistic cache patch — reflects the thumbnail change immediately in every
      // visible list/tree/detail view without waiting for the refetch to complete.
      // Backend now write-through updates OpenSearch, so subsequent refetches are
      // consistent as well.
      const { thumbnailType, thumbnailValue, thumbnailUrl, updatedAt } = response.data;
      patchCollectionInCache(queryClient, collectionId, {
        thumbnailType,
        thumbnailValue: thumbnailValue ?? undefined,
        thumbnailUrl,
        ...(updatedAt ? { updatedAt } : {}),
      });

      // Invalidate so natural refetches pull any server-side derived fields
      // we didn't patch locally. Covers the paginated `list(...)` caches,
      // `allCollections()`, shared-with-me / shared-by-me siblings, and the
      // single-detail cache for this collection.
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shared(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.sharedWithMe(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.sharedByMe(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(collectionId),
      });
    },
  });
};

/**
 * Hook to delete a collection thumbnail
 */
export const useDeleteCollectionThumbnail = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<void, Error, string>({
    mutationFn: async (collectionId) => {
      try {
        await apiClient.delete(API_ENDPOINTS.COLLECTIONS.THUMBNAIL(collectionId));
      } catch (error) {
        logger.error("Delete collection thumbnail error:", error);
        const message = getApiErrorMessage(error, "Failed to remove collection thumbnail");
        showError(message);
        throw new Error(message);
      }
    },
    onSuccess: (_, collectionId) => {
      // Optimistic cache patch — clear thumbnail fields everywhere it's visible.
      patchCollectionInCache(queryClient, collectionId, {
        thumbnailType: undefined,
        thumbnailValue: undefined,
        thumbnailUrl: undefined,
      });

      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shared(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.sharedWithMe(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.sharedByMe(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(collectionId),
      });
    },
  });
};

/**
 * Hook to set a collection thumbnail to an icon
 * This uses the PATCH endpoint to set thumbnailType: 'icon' and thumbnailValue: iconName
 */
export const useSetCollectionIcon = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<CollectionResponse, Error, { collectionId: string; iconName: string }>({
    mutationFn: async ({ collectionId, iconName }) => {
      try {
        const response = await apiClient.patch<CollectionResponse>(
          API_ENDPOINTS.COLLECTIONS.UPDATE(collectionId),
          {
            thumbnailType: "icon",
            thumbnailValue: iconName,
          }
        );
        return response.data;
      } catch (error) {
        logger.error("Set collection icon error:", error);
        const message = getApiErrorMessage(error, "Failed to set collection icon");
        showError(message);
        throw new Error(message);
      }
    },
    onSuccess: (response, { collectionId, iconName }) => {
      // Optimistic cache patch — icons render from (thumbnailType=icon, thumbnailValue=name)
      // in the frontend without needing a thumbnailUrl. Clear any prior thumbnailUrl so
      // the `<img>` doesn't keep pointing at the old upload.
      const updatedAt = response?.data?.updatedAt;
      patchCollectionInCache(queryClient, collectionId, {
        thumbnailType: "icon",
        thumbnailValue: iconName,
        thumbnailUrl: undefined,
        ...(updatedAt ? { updatedAt } : {}),
      });

      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shared(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.sharedWithMe(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.sharedByMe(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.detail(collectionId),
      });
    },
  });
};
