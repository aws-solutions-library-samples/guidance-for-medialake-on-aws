import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";
import { CustomMetadataApiFilter } from "@/types/facetSearch";

interface SearchParams {
  page?: number;
  pageSize?: number;
  isSemantic?: boolean;
  searchModes?: ("visual" | "audio" | "transcript")[];
  // Sorting parameters
  sortBy?: "createdAt" | "name" | "size" | "type" | "format";
  sortDirection?: "asc" | "desc";
  // New facet parameters
  type?: string;
  extension?: string;
  LargerThan?: number;
  asset_size_lte?: number;
  asset_size_gte?: number;
  ingested_date_lte?: string;
  ingested_date_gte?: string;
  filename?: string;
  fields?: string[];
  customMetadataFilters?: CustomMetadataApiFilter[];
}

export interface FacetBucket {
  key: string;
  doc_count: number;
}

export interface FieldAggregation {
  buckets?: FacetBucket[];
  min?: number | string;
  max?: number | string;
}

interface SearchResponseData {
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
    facets: any;
    suggestions: any;
  };
  results: Array<any>;
  totalResults: number;
  facets: any;
  suggestions: any;
  aggregations?: Record<string, FieldAggregation>;
  facetsInfo?: { limited: boolean };
}

export interface SearchResponseType {
  status: string;
  message: string;
  data: SearchResponseData | null;
}

export interface SearchError extends Error {
  apiResponse?: SearchResponseType;
}

export const useSearch = (query: string, params?: SearchParams) => {
  const page = params?.page || 1;
  const pageSize = params?.pageSize || 20;
  const isSemantic = params?.isSemantic ?? false;
  const searchModes = params?.searchModes || ["visual"];
  const fields = params?.fields || [];
  const sortBy = params?.sortBy;
  const sortDirection = params?.sortDirection || "desc";

  // Construct the sort parameter (e.g., "-createdAt" for descending)
  const sort = sortBy ? `${sortDirection === "desc" ? "-" : ""}${sortBy}` : undefined;

  // Extract facet parameters from params
  const facetParams = params
    ? {
        type: params.type,
        extension: params.extension,
        LargerThan: params.LargerThan,
        asset_size_lte: params.asset_size_lte,
        asset_size_gte: params.asset_size_gte,
        ingested_date_lte: params.ingested_date_lte,
        ingested_date_gte: params.ingested_date_gte,
        filename: params.filename,
        customMetadataFilters: params.customMetadataFilters,
      }
    : undefined;

  return useQuery<SearchResponseType, SearchError>({
    queryKey: QUERY_KEYS.SEARCH.list(
      query,
      page,
      pageSize,
      isSemantic,
      fields,
      facetParams,
      sort,
      searchModes
    ),
    queryFn: async ({ signal }) => {
      try {
        // Build query parameters
        const queryParams = new URLSearchParams();
        queryParams.append("q", query);
        queryParams.append("page", page.toString());
        queryParams.append("pageSize", pageSize.toString());
        queryParams.append("semantic", isSemantic.toString());

        // Add searchModality for semantic search (Marengo 3.0 multi-modal)
        if (isSemantic && searchModes.length > 0) {
          queryParams.append("searchModality", searchModes.join(","));
        }

        // Add sort parameter if specified
        if (sort) queryParams.append("sort", sort);

        // Add facet parameters if they exist
        if (params?.type) queryParams.append("type", params.type);
        if (params?.extension) queryParams.append("extension", params.extension);
        if (params?.LargerThan) queryParams.append("LargerThan", params.LargerThan.toString());
        if (params?.asset_size_lte)
          queryParams.append("asset_size_lte", params.asset_size_lte.toString());
        if (params?.asset_size_gte)
          queryParams.append("asset_size_gte", params.asset_size_gte.toString());
        if (params?.ingested_date_lte)
          queryParams.append("ingested_date_lte", params.ingested_date_lte);
        if (params?.ingested_date_gte)
          queryParams.append("ingested_date_gte", params.ingested_date_gte);
        if (params?.filename) queryParams.append("filename", params.filename);

        // Add custom metadata filters as JSON
        if (params?.customMetadataFilters && params.customMetadataFilters.length > 0) {
          queryParams.append("filters", JSON.stringify(params.customMetadataFilters));
        }

        // Add fields to the query parameters
        if (params?.fields && params.fields.length > 0) {
          // Use the short field names directly
          params.fields.forEach((field) => {
            queryParams.append("fields", field);
          });
        }

        const response = await apiClient.get<SearchResponseType>(
          `${API_ENDPOINTS.SEARCH}?${queryParams.toString()}`,
          { signal }
        );

        // Check if the response status is not a success (2xx)
        if (response.data?.status && !response.data.status.startsWith("2")) {
          const error = new Error(response.data.message || "Search request failed") as SearchError;
          error.apiResponse = response.data;
          throw error;
        }

        if (!response.data?.data?.results) {
          throw new Error("Invalid search response structure");
        }

        return response.data;
      } catch (error) {
        // Silently ignore canceled requests (expected during debounce/re-renders)
        if (axios.isCancel(error)) {
          throw error;
        }

        logger.error("Search error:", error);

        // Handle axios errors
        if (axios.isAxiosError(error) && error.response?.data) {
          const apiError = new Error(
            error.response.data.message || "Search request failed"
          ) as SearchError;
          apiError.apiResponse = error.response.data;
          throw apiError;
        }

        // Rethrow the error to be handled by the component
        throw error;
      }
    },
    placeholderData: keepPreviousData,
    staleTime: 1000 * 30, // 30 seconds — data is fresh for half a minute, then refetches on next mount
    gcTime: 1000 * 60 * 5, // Keep unused results for 5 minutes for back-navigation
    refetchOnMount: true, // Refetch when a new component mounts with this query
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
};
