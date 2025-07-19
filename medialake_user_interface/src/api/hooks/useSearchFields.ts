import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";

export interface FieldInfo {
  name: string;
  displayName: string;
  description: string;
  type: string;
  isDefault: boolean;
}

export interface SearchFieldsData {
  defaultFields: FieldInfo[];
  availableFields: FieldInfo[];
}

export interface SearchFieldsResponseType {
  status: string;
  message: string;
  data: SearchFieldsData | null;
}

export interface SearchFieldsError extends Error {
  apiResponse?: SearchFieldsResponseType;
}

export const useSearchFields = () => {
  return useQuery<SearchFieldsResponseType, SearchFieldsError>({
    queryKey: QUERY_KEYS.SEARCH.fields(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<SearchFieldsResponseType>(
          `${API_ENDPOINTS.SEARCH}/fields`,
          { signal },
        );

        // Check if the response status is not a success (2xx)
        if (response.data?.status && !response.data.status.startsWith("2")) {
          const error = new Error(
            response.data.message || "Search fields request failed",
          ) as SearchFieldsError;
          error.apiResponse = response.data;
          throw error;
        }

        if (!response.data?.data?.availableFields) {
          throw new Error("Invalid search fields response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Search fields error:", error);

        // Handle axios errors
        if (axios.isAxiosError(error) && error.response?.data) {
          const apiError = new Error(
            error.response.data.message || "Search fields request failed",
          ) as SearchFieldsError;
          apiError.apiResponse = error.response.data;
          throw apiError;
        }

        // Rethrow the error to be handled by the component
        throw error;
      }
    },
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    gcTime: 1000 * 60 * 10, // Keep unused data for 10 minutes
  });
};
