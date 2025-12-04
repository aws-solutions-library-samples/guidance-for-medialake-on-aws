import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";

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
  sharedWith?: string[];
  ancestors?: Array<{
    id: string;
    name: string;
    parentId?: string;
  }>;
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
}

export interface UpdateCollectionRequest {
  name?: string;
  description?: string;
  parentId?: string;
  isPublic?: boolean;
  collectionTypeId?: string;
}

export interface ShareCollectionRequest {
  userId?: string;
  groupId?: string;
  role: "viewer" | "editor" | "admin";
  expiresAt?: string;
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
  metadata?: Record<string, any>;
}

export interface CollectionShare {
  id: string;
  collectionId: string;
  userId?: string;
  groupId?: string;
  role: string;
  expiresAt?: string;
  createdAt: string;
  sharedBy: string;
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

// Hook to get all collections for the current user
export const useGetCollections = (filters?: Record<string, any>) => {
  const { showError } = useErrorModal();

  return useQuery<CollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.list(filters),
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
          ? `${API_ENDPOINTS.COLLECTIONS.BASE}?${params}`
          : API_ENDPOINTS.COLLECTIONS.BASE;

        const response = await apiClient.get<CollectionsResponse>(url, {
          signal,
        });
        return response.data;
      } catch (error) {
        logger.error("Fetch collections error:", error);
        showError("Failed to fetch collections");
        throw error;
      }
    },
  });
};

// Hook to get shared collections
export const useGetSharedCollections = () => {
  const { showError } = useErrorModal();

  return useQuery<CollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.shared(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionsResponse>(
          API_ENDPOINTS.COLLECTIONS.SHARED,
          { signal }
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch shared collections error:", error);
        showError("Failed to fetch shared collections");
        throw error;
      }
    },
  });
};

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

  return useQuery<CollectionsResponse, Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.children(parentId),
    enabled: enabled && !!parentId,
    placeholderData: keepPreviousData, // Keep previous children visible during navigation
    queryFn: async ({ signal }) => {
      try {
        const params = new URLSearchParams();
        params.append("filter[parentId]", parentId);

        const response = await apiClient.get<CollectionsResponse>(
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
    onSuccess: () => {
      // Invalidate and refetch collections list
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
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
        showError("Failed to update collection");
        throw error;
      }
    },
    onSuccess: (data, { id }) => {
      // Invalidate collections list and specific collection
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
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
    onSuccess: () => {
      // Invalidate collections list
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.COLLECTIONS.shared(),
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
      // Invalidate collections list and specific collection details
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
// Collection Types Hooks
// =============================================================================

/**
 * Hook to fetch all collection types
 */
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
