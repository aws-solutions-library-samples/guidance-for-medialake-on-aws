import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import queryClient from '@/api/queryClient';
import { PipelinesService } from './pipelinesService';
import type { Pipeline, PipelinesResponse, CreatePipelineDto, UpdatePipelineDto } from '../types/pipelines.types';

interface PipelineError {
    status?: number;
    message: string;
}

const PIPELINES_QUERY_KEYS = {
    all: ['pipelines'] as const,
    list: () => [...PIPELINES_QUERY_KEYS.all, 'list'] as const,
    detail: (id: string) => [...PIPELINES_QUERY_KEYS.all, 'detail', id] as const,
};

export const useGetPipelines = (
    options?: Omit<UseQueryOptions<PipelinesResponse, PipelineError>, 'queryKey' | 'queryFn'>
) => {
    return useQuery({
        queryKey: PIPELINES_QUERY_KEYS.list(),
        queryFn: () => PipelinesService.getPipelines(),
        // Add optimizations to prevent unnecessary refetching
        staleTime: 5 * 60 * 1000, // 5 minutes
        gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        ...options
    });
};

export const useGetPipeline = (
    id: string,
    options?: Omit<UseQueryOptions<Pipeline, PipelineError>, 'queryKey' | 'queryFn'>
) => {
    return useQuery({
        queryKey: PIPELINES_QUERY_KEYS.detail(id),
        queryFn: () => PipelinesService.getPipeline(id),
        enabled: !!id,
        ...options
    });
};

export const useCreatePipeline = (
    options?: Omit<UseMutationOptions<Pipeline, PipelineError, CreatePipelineDto>, 'mutationFn'>
) => {
    return useMutation({
        mutationFn: (data: CreatePipelineDto) => PipelinesService.createPipeline(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
        },
        ...options
    });
};

export const useUpdatePipeline = (
    options?: Omit<UseMutationOptions<Pipeline, PipelineError, { id: string; data: UpdatePipelineDto }>, 'mutationFn'>
) => {
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: UpdatePipelineDto }) =>
            PipelinesService.updatePipeline(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.detail(id) });
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
        },
        ...options
    });
};

export const useDeletePipeline = (
    options?: Omit<UseMutationOptions<void, PipelineError, string>, 'mutationFn'>
) => {
    return useMutation({
        mutationFn: async (id: string) => {
            console.log(`[pipelinesController] Starting delete mutation for pipeline ID: ${id}`);

            // Create a timeout promise to prevent hanging
            const timeoutPromise = new Promise<never>((_, reject) => {
                setTimeout(() => {
                    console.error(`[pipelinesController] Delete request timed out after 30 seconds for pipeline ID: ${id}`);
                    reject(new Error('Delete request timed out after 30 seconds'));
                }, 30000);
            });

            try {
                // Race the deletion against the timeout
                await Promise.race([
                    PipelinesService.deletePipeline(id),
                    timeoutPromise
                ]);

                console.log(`[pipelinesController] Delete mutation completed successfully for pipeline ID: ${id}`);
            } catch (error) {
                console.error(`[pipelinesController] Delete mutation failed for pipeline ID: ${id}`, error);

                // Convert the error to a PipelineError format
                const pipelineError: PipelineError = {
                    message: error instanceof Error ? error.message : 'Unknown error occurred during pipeline deletion',
                    status: error?.response?.status
                };

                // Log additional details if available
                if (error?.response?.data) {
                    console.error('[pipelinesController] API error details:', error.response.data);
                }

                throw pipelineError;
            }
        },
        onSuccess: (_, id) => {
            console.log(`[pipelinesController] Invalidating queries after successful deletion of pipeline: ${id}`);
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.detail(id) });
        },
        onError: (error, id) => {
            console.error(`[pipelinesController] Error in delete mutation for pipeline ${id}:`, error);
        },
        // No retries for deletion to avoid multiple delete attempts
        retry: false,
        ...options
    });
};

export const useStartPipeline = (
    options?: Omit<UseMutationOptions<void, PipelineError, string>, 'mutationFn'>
) => {
    return useMutation({
        mutationFn: (id: string) => PipelinesService.startPipeline(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.detail(id) });
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
        },
        ...options
    });
};

export const useStopPipeline = (
    options?: Omit<UseMutationOptions<void, PipelineError, string>, 'mutationFn'>
) => {
    return useMutation({
        mutationFn: (id: string) => PipelinesService.stopPipeline(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.detail(id) });
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
        },
        ...options
    });
};
