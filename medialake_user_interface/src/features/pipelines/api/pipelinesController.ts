import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { PipelinesService } from "./pipelinesService";
import type {
  Pipeline,
  PipelinesResponse,
  CreatePipelineDto,
  UpdatePipelineDto,
} from "../types/pipelines.types";

interface PipelineError {
  status?: number;
  message: string;
}

const PIPELINES_QUERY_KEYS = {
  all: ["pipelines"] as const,
  list: () => [...PIPELINES_QUERY_KEYS.all, "list"] as const,
  optionalList: () => [...PIPELINES_QUERY_KEYS.all, "list", "optional"] as const,
  detail: (id: string) => [...PIPELINES_QUERY_KEYS.all, "detail", id] as const,
};

const emptyPipelinesResponse = (): PipelinesResponse => ({
  status: "200",
  message: "ok",
  data: {
    searchMetadata: { totalResults: 0, pageSize: 0, nextToken: null },
    s: [],
  },
});

export const useGetPipelines = (
  options?: Omit<UseQueryOptions<PipelinesResponse, PipelineError>, "queryKey" | "queryFn">
) => {
  return useQuery({
    queryKey: PIPELINES_QUERY_KEYS.list(),
    queryFn: () => PipelinesService.getPipelines(),
    // Refresh every 15 seconds to check for pipeline status updates
    refetchInterval: 15 * 1000, // 15 seconds
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
    refetchOnWindowFocus: true,
    refetchOnMount: true,
    ...options,
  });
};

/**
 * List pipelines from a surface where pipelines are *optional* — i.e. the
 * feature is a bonus on a screen that must keep working without it (the batch
 * operations sidebar being the motivating case).
 *
 * Differences from `useGetPipelines`:
 *  - Callers are expected to pass `enabled` from a permission check so no
 *    request is made at all when the user lacks `pipelines:view`.
 *  - A 403 resolves to an empty list instead of tripping the global
 *    /access-denied redirect, so a stale token or a frontend/authorizer
 *    permission mismatch can't eject the user from the page they are on.
 *  - No background polling — these surfaces only need the list once.
 *
 * It deliberately uses its own query key so this tolerant behaviour never
 * leaks into the pipelines management screens, which should surface real errors.
 */
export const useGetPipelinesOptional = (
  options?: Omit<UseQueryOptions<PipelinesResponse, PipelineError>, "queryKey" | "queryFn">
) => {
  return useQuery({
    queryKey: PIPELINES_QUERY_KEYS.optionalList(),
    queryFn: async () => {
      try {
        return await PipelinesService.getPipelines({
          skipAccessDeniedRedirect: true,
        });
      } catch (error) {
        if ((error as { response?: { status?: number } })?.response?.status === 403) {
          // Fresh object per call — a shared constant could be mutated by a
          // consumer and would then poison every later 403.
          return emptyPipelinesResponse();
        }
        throw error;
      }
    },
    staleTime: 60 * 1000,
    gcTime: 10 * 60 * 1000,
    retry: false,
    ...options,
  });
};

export const useGetPipeline = (
  id: string,
  options?: Omit<UseQueryOptions<Pipeline, PipelineError>, "queryKey" | "queryFn">
) => {
  return useQuery({
    queryKey: PIPELINES_QUERY_KEYS.detail(id),
    queryFn: () => PipelinesService.getPipeline(id),
    enabled: !!id,
    ...options,
  });
};

export const useCreatePipeline = (
  options?: Omit<
    UseMutationOptions<
      {
        pipeline_id: string;
        execution_arn: string;
        status: string;
        pipeline_name: string;
        message: string;
      },
      PipelineError,
      CreatePipelineDto
    >,
    "mutationFn"
  >
) => {
  return useMutation({
    mutationFn: (data: CreatePipelineDto) => PipelinesService.createPipeline(data),
    ...options,
  });
};

export const useGetPipelineStatus = (
  executionArn: string,
  options?: Omit<
    UseQueryOptions<
      {
        execution_arn: string;
        step_function_status: string;
        step_function_output: any;
        pipeline: Pipeline | null;
      },
      PipelineError
    >,
    "queryKey" | "queryFn"
  >
) => {
  return useQuery({
    queryKey: [...PIPELINES_QUERY_KEYS.all, "status", executionArn],
    queryFn: () => PipelinesService.getPipelineStatus(executionArn),
    enabled: !!executionArn,
    ...options,
  });
};

export const useUpdatePipeline = (
  options?: Omit<
    UseMutationOptions<Pipeline, PipelineError, { id: string; data: UpdatePipelineDto }>,
    "mutationFn"
  >
) => {
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdatePipelineDto }) =>
      PipelinesService.updatePipeline(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: PIPELINES_QUERY_KEYS.detail(id),
      });
      queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
    },
    ...options,
  });
};

export const useDeletePipeline = (
  options?: Omit<UseMutationOptions<void, PipelineError, string>, "mutationFn">
) => {
  return useMutation({
    mutationFn: async (id: string) => {
      // Create a timeout promise to prevent hanging
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => {
          console.error(
            `[pipelinesController] Delete request timed out after 30 seconds for pipeline ID: ${id}`
          );
          reject(new Error("Delete request timed out after 30 seconds"));
        }, 30000);
      });

      try {
        // Race the deletion against the timeout
        await Promise.race([PipelinesService.deletePipeline(id), timeoutPromise]);
      } catch (error) {
        console.error(`[pipelinesController] Delete mutation failed for pipeline ID: ${id}`, error);

        // Convert the error to a PipelineError format
        const pipelineError: PipelineError = {
          message:
            error instanceof Error
              ? error.message
              : "Unknown error occurred during pipeline deletion",
          status: error?.response?.status,
        };

        // Log additional details if available
        if (error?.response?.data) {
          console.error("[pipelinesController] API error details:", error.response.data);
        }

        throw pipelineError;
      }
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
      queryClient.invalidateQueries({
        queryKey: PIPELINES_QUERY_KEYS.detail(id),
      });
    },
    onError: (error, id) => {
      console.error(`[pipelinesController] Error in delete mutation for pipeline ${id}:`, error);
    },
    // No retries for deletion to avoid multiple delete attempts
    retry: false,
    ...options,
  });
};

export const useStartPipeline = (
  options?: Omit<UseMutationOptions<void, PipelineError, string>, "mutationFn">
) => {
  return useMutation({
    mutationFn: (id: string) => PipelinesService.startPipeline(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: PIPELINES_QUERY_KEYS.detail(id),
      });
      queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
    },
    ...options,
  });
};

export const useStopPipeline = (
  options?: Omit<UseMutationOptions<void, PipelineError, string>, "mutationFn">
) => {
  return useMutation({
    mutationFn: (id: string) => PipelinesService.stopPipeline(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({
        queryKey: PIPELINES_QUERY_KEYS.detail(id),
      });
      queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
    },
    ...options,
  });
};
