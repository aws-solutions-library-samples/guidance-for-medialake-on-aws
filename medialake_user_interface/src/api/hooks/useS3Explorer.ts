import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";
import type { ApiResponse, S3ListObjectsResponse } from "../types/api.types";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";

/**
 * S3Explorer performance optimization configuration
 * - Increased stale time to reduce API calls
 * - Extended cache time to improve UX during navigation
 * - Set refetchOnMount to "always" for most up-to-date data when component remounts
 * - Added retry logic with exponential backoff for reliability
 */
const defaultQueryConfig = {
  staleTime: 5 * 60 * 1000, // 5 minutes instead of 30 seconds
  cacheTime: 10 * 60 * 1000, // 10 minutes
  retry: 3,
  refetchOnMount: "always" as const, // Using literal type for proper typing
  refetchOnWindowFocus: false,
  retryDelay: (attemptIndex: number) =>
    Math.min(1000 * 2 ** attemptIndex, 30000),
};

interface S3ExplorerParams {
  connectorId: string;
  prefix?: string;
  delimiter?: string;
  continuationToken?: string | null;
}

/**
 * Hook to fetch S3 bucket contents with performance optimizations:
 * 1. Client-side caching with appropriate stale times
 * 2. Performance tracking and logging
 * 3. HTTP cache headers to leverage browser caching
 * 4. Error handling with user feedback
 */
export const useS3Explorer = ({
  connectorId,
  prefix = "",
  delimiter = "/",
  continuationToken = null,
}: S3ExplorerParams) => {
  const { showError } = useErrorModal();

  // Add performance tracking
  const startTime = React.useRef<number>(0);

  React.useEffect(() => {
    startTime.current = performance.now();
    return () => {
      const loadTime = performance.now() - startTime.current;
      logger.debug(`S3Explorer load time: ${loadTime}ms for path ${prefix}`);
    };
  }, [prefix]);

  return useQuery<ApiResponse<S3ListObjectsResponse>, Error>({
    queryKey: QUERY_KEYS.CONNECTORS.s3.explorer(
      connectorId,
      prefix,
      continuationToken,
    ),
    queryFn: async ({ signal }) => {
      try {
        // Log request start time
        const requestStart = performance.now();

        const response = await apiClient.get<
          ApiResponse<S3ListObjectsResponse>
        >(`${API_ENDPOINTS.CONNECTORS}/s3/explorer/${connectorId}`, {
          params: {
            prefix,
            delimiter,
            continuationToken,
          },
          signal,
          // Add HTTP cache control headers aligned with our stale time
          headers: {
            "Cache-Control": "max-age=300", // 5 minutes cache
          },
        });

        // Log request duration
        const requestDuration = performance.now() - requestStart;
        logger.debug(
          `S3Explorer API call took ${requestDuration}ms for path ${prefix}`,
        );

        return response.data;
      } catch (error) {
        logger.error("S3 Explorer error:", error);
        showError("Failed to fetch S3 contents");
        throw error;
      }
    },
    enabled: !!connectorId,
    ...defaultQueryConfig,
  });
};

/**
 * Prefetch folder contents when hovering over folders
 * This improves perceived performance by loading potential
 * navigation targets before the user clicks
 */
export const prefetchS3FolderContents = (
  connectorId: string,
  prefix: string,
) => {
  const queryClient = useQueryClient();
  return queryClient.prefetchQuery({
    queryKey: QUERY_KEYS.CONNECTORS.s3.explorer(connectorId, prefix, null),
    queryFn: async ({ signal }) => {
      const response = await apiClient.get<ApiResponse<S3ListObjectsResponse>>(
        `${API_ENDPOINTS.CONNECTORS}/s3/explorer/${connectorId}`,
        {
          params: { prefix, delimiter: "/" },
          headers: {
            "Cache-Control": "max-age=300", // Match our stale time
          },
          signal,
        },
      );
      return response.data;
    },
    ...defaultQueryConfig,
  });
};
