import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";
import {
  type ImageItem,
  type VideoItem,
  type AudioItem,
} from "@/types/search/searchResults";

type AssetItem = ImageItem | VideoItem | AudioItem;

interface ConnectorAssetsParams {
  bucketName: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDirection?: "asc" | "desc";
  assetType?: string;
}

interface ConnectorAssetsData {
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
    facets: any;
    suggestions: any;
  };
  results: AssetItem[];
  totalResults: number;
  facets: any;
  suggestions: any;
}

interface ConnectorAssetsResponse {
  status: string;
  message: string;
  data: ConnectorAssetsData | null;
}

export interface ConnectorAssetsError extends Error {
  apiResponse?: ConnectorAssetsResponse;
}

export const useConnectorAssets = ({
  bucketName,
  page = 1,
  pageSize = 50,
  sortBy = "createdAt",
  sortDirection = "desc",
  assetType,
}: ConnectorAssetsParams) => {
  const { showError } = useErrorModal();

  // Construct the query string for bucket search
  const query = bucketName
    ? `storageIdentifier:${bucketName}${assetType ? ` type:${assetType}` : ""}`
    : "";

  // Construct the sort parameter
  const sort = sortBy
    ? `${sortDirection === "desc" ? "-" : ""}${sortBy}`
    : undefined;

  // For debugging
  console.log("useConnectorAssets called with:", { bucketName, query });

  return useQuery<ConnectorAssetsResponse, ConnectorAssetsError>({
    // Use the existing search list query key with our bucket filter
    queryKey: QUERY_KEYS.SEARCH.list(query, page, pageSize, false),
    queryFn: async ({ signal }) => {
      try {
        // Build the query parameters
        const params: Record<string, string | number | boolean> = {
          q: query,
          page,
          pageSize,
          semantic: false,
        };

        if (sort) {
          params.sort = sort;
        }

        const response = await apiClient.get<ConnectorAssetsResponse>(
          API_ENDPOINTS.SEARCH,
          {
            params,
            signal,
          },
        );

        // Check if the response status is not a success (2xx)
        if (response.data?.status && !response.data.status.startsWith("2")) {
          const error = new Error(
            response.data.message || "Search request failed",
          ) as ConnectorAssetsError;
          error.apiResponse = response.data;
          throw error;
        }

        if (!response.data?.data?.results) {
          throw new Error("Invalid search response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Connector assets error:", error);

        // Handle axios errors
        if (axios.isAxiosError(error) && error.response?.data) {
          const apiError = new Error(
            error.response.data.message || "Search request failed",
          ) as ConnectorAssetsError;
          apiError.apiResponse = error.response.data;
          throw apiError;
        }

        // Rethrow the error to be handled by the component
        throw error;
      }
    },
    staleTime: 1000 * 60, // Cache for 1 minute
    gcTime: 1000 * 60 * 5, // Keep unused data for 5 minutes
    enabled: !!bucketName && bucketName.trim() !== "", // Only enable and refetch if there is a valid bucket name
  });
};

export type { AssetItem, ConnectorAssetsResponse, ConnectorAssetsData };
