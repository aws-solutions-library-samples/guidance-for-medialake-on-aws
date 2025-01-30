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
        mutationFn: (id: string) => PipelinesService.deletePipeline(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: PIPELINES_QUERY_KEYS.list() });
        },
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