import { useMutation } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";

import type {
  CreatePipelineRequest,
  PipelineResponse,
  PipelineListResponse,
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
      const response = await apiClient.post<PipelineResponse>(API_ENDPOINTS.PIPELINES, data);
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
      queryClient.setQueryData<PipelineListResponse>([QUERY_KEYS.PIPELINES], (old) => {
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
      });
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
      queryClient.setQueryData<PipelineListResponse>([QUERY_KEYS.PIPELINES], (old) => {
        if (!old) return old;
        return {
          ...old,
          data: {
            ...old.data,
            pipelines: old.data.pipelines.filter((pipeline) => pipeline.id !== deletedPipelineId),
          },
        };
      });
    },
  });
};

// The token-paginated `usePipeline` infinite query that used to live here was
// never imported, and GET /pipelines now returns the full list in one response
// so the UI can sort, filter and paginate across every pipeline. Pipelines are
// fetched via `features/pipelines/api/pipelinesController.useGetPipelines`.
