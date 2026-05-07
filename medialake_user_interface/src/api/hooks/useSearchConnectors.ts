/**
 * Hook to fetch connector summaries via the search API.
 *
 * This avoids requiring the separate `connectors:view` permission —
 * the `/search/connectors` endpoint is gated by `search:view` instead,
 * so any user who can browse assets can also see the connector list.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";

/**
 * Lightweight connector summary returned by /search/connectors.
 * Contains only the fields needed for the Assets page sidebar
 * and the File Uploader destination picker.
 */
export interface ConnectorSummary {
  id: string;
  name: string;
  type: string;
  storageIdentifier: string;
  status: string;
  objectPrefix?: string | string[];
  region?: string;
  configuration?: {
    objectPrefix?: string | string[];
    allowUploads?: boolean;
  };
}

interface SearchConnectorsResponse {
  status: string;
  message: string;
  data: {
    connectors: ConnectorSummary[];
  };
}

export const useSearchConnectors = () => {
  return useQuery<SearchConnectorsResponse, Error>({
    queryKey: [...QUERY_KEYS.SEARCH.all, "connectors"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<SearchConnectorsResponse>(
          API_ENDPOINTS.SEARCH_CONNECTORS,
          { signal, skipAccessDeniedRedirect: true } as any
        );
        return response.data;
      } catch (error: any) {
        // Gracefully degrade on 403 — return empty list instead of
        // triggering the global access-denied redirect
        if (error?.response?.status === 403) {
          logger.warn("No permission for search connectors, returning empty list");
          return {
            status: "200",
            message: "ok",
            data: { connectors: [] },
          };
        }
        logger.error("Fetch search connectors error:", error);
        throw error;
      }
    },
  });
};
