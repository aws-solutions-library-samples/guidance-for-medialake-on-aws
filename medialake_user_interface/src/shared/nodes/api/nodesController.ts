import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { NodesService } from './nodesService';
import { NodesResponse, NodesError } from '../types/nodes.types';

export const NODES_QUERY_KEYS = {
    all: ['nodes'] as const,
    list: () => [...NODES_QUERY_KEYS.all, 'list'] as const,
    detail: (nodeId: string) => [...NODES_QUERY_KEYS.all, 'detail', nodeId] as const,
};

export const useGetNodes = (options?: Omit<UseQueryOptions<NodesResponse, NodesError, NodesResponse>, 'queryKey' | 'queryFn'>) => {
    return useQuery({
        queryKey: NODES_QUERY_KEYS.list(),
        queryFn: () => NodesService.getNodes(),
        retry: (failureCount, error: NodesError) => {
            // Don't retry on 4xx errors
            if (error.status?.toString().startsWith('4')) {
                return false;
            }
            return failureCount < 3;
        },
        ...options
    });
};

export const useGetNode = (nodeId: string) => {
    return useQuery({
        queryKey: NODES_QUERY_KEYS.detail(nodeId),
        queryFn: () => NodesService.getNode(nodeId),
        enabled: !!nodeId,
        retry: (failureCount, error: NodesError) => {
            if (error.status?.toString().startsWith('4')) {
                return false;
            }
            return failureCount < 3;
        },
    });
}; 