import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { apiClient } from '@/api/apiClient';
import { API_ENDPOINTS } from '@/api/endpoints';
import { logger } from '@/common/helpers/logger';
import { useErrorModal } from '@/hooks/useErrorModal';

interface SearchParams {
    page?: number;
    pageSize?: number;
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
}

interface SearchResponseType {
    status: string;
    message: string;
    data: SearchResponseData;
}

export const useSearch = (query: string, params?: SearchParams) => {
    const page = params?.page || 1;
    const pageSize = params?.pageSize || 20;
    const { showError } = useErrorModal();

    return useQuery<SearchResponseType>({
        queryKey: ['search', query, page, pageSize],
        queryFn: async ({ signal }) => {
            try {
                const response = await apiClient.get<SearchResponseType>(
                    `${API_ENDPOINTS.SEARCH}?q=${encodeURIComponent(query)}&page=${page}&pageSize=${pageSize}`,
                    { signal }
                );

                if (!response.data?.data?.results) {
                    throw new Error('Invalid search response structure');
                }

                return response.data;
            } catch (error) {
                logger.error('Search error:', error);
                showError('Failed to perform search');
                throw error;
            }
        },
        placeholderData: keepPreviousData,
        enabled: !!query,
        staleTime: 0,
        gcTime: 0
    });
};
