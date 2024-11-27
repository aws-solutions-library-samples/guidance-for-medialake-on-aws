import { useInfiniteQuery } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { logger } from '../../common/helpers/logger';
import { useErrorModal } from '../../hooks/useErrorModal';
import type { PipelineExecutionsResponse, PipelineExecutionFilters } from '../types/pipelineExecutions.types';

export const usePipelineExecutions = (
    pageSize: number = 20,
    filters?: PipelineExecutionFilters
) => {
    const { showError } = useErrorModal();

    return useInfiniteQuery<PipelineExecutionsResponse, Error>({
        queryKey: [QUERY_KEYS.PIPELINE_EXECUTIONS.all, { pageSize, filters }],
        initialPageParam: 1,
        queryFn: async ({ pageParam }) => {
            try {
                const params = new URLSearchParams({
                    page: pageParam.toString(),
                    pageSize: pageSize.toString(),
                    ...(filters?.status && { status: filters.status }),
                    ...(filters?.startDate && { startDate: filters.startDate }),
                    ...(filters?.endDate && { endDate: filters.endDate }),
                    ...(filters?.sortBy && { sortBy: filters.sortBy }),
                    ...(filters?.sortOrder && { sortOrder: filters.sortOrder }),
                });

                const response = await apiClient.get<PipelineExecutionsResponse>(
                    `${API_ENDPOINTS.PIPELINE_EXECUTIONS}?${params.toString()}`
                );
                return response.data;
            } catch (error) {
                logger.error('Fetch pipeline executions error:', error);
                showError('Failed to fetch pipeline executions');
                throw error;
            }
        },
        getNextPageParam: (lastPage, pages) => {
            const { searchMetadata } = lastPage.data;
            const totalPages = Math.ceil(searchMetadata.totalResults / searchMetadata.pageSize);
            if (searchMetadata.page < totalPages) {
                return searchMetadata.page + 1;
            }
            return undefined;
        },
        getPreviousPageParam: (firstPage, pages) => {
            if (firstPage.data.searchMetadata.page > 1) {
                return firstPage.data.searchMetadata.page - 1;
            }
            return undefined;
        },
    });
};
