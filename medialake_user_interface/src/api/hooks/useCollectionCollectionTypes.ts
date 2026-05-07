/**
 * Hook to fetch collection type summaries via the collections API.
 *
 * This avoids requiring the separate `collection-types:view` permission —
 * the `/collections/collection-types` endpoint is gated by `collections:view`
 * instead, so any user who can browse collections can also see type metadata.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import type { CollectionTypesResponse } from "@/api/hooks/useCollections";

export const useCollectionCollectionTypes = () => {
  return useQuery<CollectionTypesResponse, Error>({
    queryKey: [...QUERY_KEYS.COLLECTIONS.lists(), "collection-types"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionTypesResponse>(
          API_ENDPOINTS.COLLECTIONS.COLLECTION_TYPES,
          { signal, skipAccessDeniedRedirect: true } as any
        );
        return response.data;
      } catch (error: any) {
        if (error?.response?.status === 403) {
          logger.warn("No permission for collections collection-types, returning empty list");
          return {
            success: true,
            data: [],
            pagination: { has_next_page: false, has_prev_page: false, limit: 0 },
            meta: { timestamp: new Date().toISOString(), version: "v1", request_id: "" },
          } as CollectionTypesResponse;
        }
        logger.error("Fetch collection collection-types error:", error);
        throw error;
      }
    },
  });
};
