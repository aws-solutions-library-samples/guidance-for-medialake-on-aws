import { useMutation } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { useInfiniteQuery } from "@tanstack/react-query";

import type {
  CreatePipelineRequest,
  PipelineResponse,
  PipelineListResponse,
  PipelineFilters,
} from "@/api/types/pipeline.types";

const validatePipelineRequest = (data: any) => {
  if (!data) {
    throw new Error("Pipeline data is required");
  }
};

export const useCreatePipeline = () => {
  const { showError } = useErrorModal();

  return useMutation<PipelineResponse, Error, CreatePipelineRequest>({
    mutationFn: async (data) => {
      validatePipelineRequest(data);
      const response = await apiClient.post<PipelineResponse>(
        API_ENDPOINTS.PIPELINES,
        data,
      );
      return response.data;
    },
    onError: (error) => {
      logger.error("Create pipeline error:", error);
      if (error.message === "Network Error") {
        showError("Unable to save pipeline - API is not available");
      } else {
        showError(`Failed to create pipeline: ${error.message}`);
      }
    },
    onSuccess: (newPipeline) => {
      queryClient.setQueryData<PipelineListResponse>(
        [QUERY_KEYS.PIPELINES],
        (old) => {
          if (!old)
            return {
              status: "success",
              message: "Pipelines retrieved successfully",
              data: { pipelines: [newPipeline] },
            };
          return {
            status: old.status,
            message: old.message,
            data: {
              ...old.data,
              connectors: [...old.data.pipelines, newPipeline],
            },
          };
        },
      );
    },
  });
};

export const useDeletePipeline = () => {
  const { showError } = useErrorModal();

  return useMutation<void, Error, string>({
    mutationFn: async (pipelineId) => {
      await apiClient.delete(`${API_ENDPOINTS.PIPELINES}/${pipelineId}`);
    },
    onError: (error) => {
      logger.error("Delete pipeline error:", error);
      if (error.message === "Network Error") {
        showError("Unable to delete pipeline - API is not available");
      } else {
        showError(`Failed to delete pipeline: ${error.message}`);
      }
    },
    onSuccess: (_, deletedPipelineId) => {
      queryClient.setQueryData<PipelineListResponse>(
        [QUERY_KEYS.PIPELINES],
        (old) => {
          if (!old) return old;
          return {
            ...old,
            data: {
              ...old.data,
              pipelines: old.data.pipelines.filter(
                (pipeline) => pipeline.id !== deletedPipelineId,
              ),
            },
          };
        },
      );
    },
  });
};

export const usePipeline = (
  pageSize: number = 20,
  filters?: PipelineFilters,
) => {
  const { showError } = useErrorModal();

  return useInfiniteQuery({
    queryKey: [QUERY_KEYS.PIPELINES.all, pageSize, filters] as const,
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
        if (filters?.system) {
          params.system = filters.system;
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
        const response = await apiClient.get<PipelineResponse>(
          `${API_ENDPOINTS.PIPELINES}?${searchParams.toString()}`,
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch pipelines error:", error);
        showError("Failed to fetch pipelines");
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
