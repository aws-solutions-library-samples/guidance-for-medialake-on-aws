import { useInfiniteQuery } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";
import type {
  PipelineExecutionsResponse,
  PipelineExecutionFilters,
} from "../types/pipelineExecutions.types";

export const usePipelineExecutions = (
  pageSize: number = 20,
  filters?: PipelineExecutionFilters,
) => {
  const { showError } = useErrorModal();

  return useInfiniteQuery({
    queryKey: [QUERY_KEYS.PIPELINE_EXECUTIONS.all, pageSize, filters] as const,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      try {
        const params: Record<string, string> = {
          pageSize: pageSize.toString(),
        };

        if (pageParam) {
          params.nextToken = pageParam;
        }
        if (filters?.status) {
          params.status = filters.status;
        }
        if (filters?.startDate) {
          params.startDate = filters.startDate;
        }
        if (filters?.endDate) {
          params.endDate = filters.endDate;
        }
        if (filters?.sortBy) {
          params.sortBy = filters.sortBy;
        }
        if (filters?.sortOrder) {
          params.sortOrder = filters.sortOrder;
        }

        const searchParams = new URLSearchParams(params);
        const response = await apiClient.get<PipelineExecutionsResponse>(
          `${API_ENDPOINTS.PIPELINE_EXECUTIONS}?${searchParams.toString()}`,
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch pipeline executions error:", error);
        showError("Failed to fetch pipeline executions");
        throw error;
      }
    },
    getNextPageParam: (lastPage) => {
      return lastPage.data.searchMetadata.nextToken || null;
    },
    select: (data) => ({
      pages: data.pages,
      pageParams: data.pageParams,
    }),
  });
};
