import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { logger } from '../../common/helpers/logger';
import { useErrorModal } from '../../hooks/useErrorModal';
import { SearchResponse, SearchOptions } from '@/types/search'

export const useSearch = (query: string, options: SearchOptions = {}) => {
    const { showError } = useErrorModal();
    const { page = 1, pageSize = 20, filters } = options;

    return useQuery({
        queryKey: [...QUERY_KEYS.SEARCH.all, query, page, pageSize, filters],
        queryFn: async ({ signal }) => {
            try {
                const params = new URLSearchParams();
                params.append('q', query);
                params.append('page', page.toString());
                params.append('pageSize', pageSize.toString());

                if (filters) {
                    if (filters.creationDate) {
                        if (filters.creationDate.before) {
                            params.append('before', filters.creationDate.before);
                        }
                        if (filters.creationDate.after) {
                            params.append('after', filters.creationDate.after);
                        }
                    }

                    Object.entries(filters.media || {}).forEach(([type, extensions]) => {
                        if (extensions && extensions.length > 0) {
                            params.append(`media_${type}`, extensions.join(','));
                        }
                    });

                    Object.entries(filters.metadata || {}).forEach(([type, values]) => {
                        if (values && values.length > 0) {
                            params.append(`metadata_${type}`, values.join(','));
                        }
                    });
                }

                const response = await apiClient.get<SearchResponse>(`${API_ENDPOINTS.SEARCH}?${params.toString()}`, { signal });
                return response.data;
            } catch (error) {
                logger.error('Search error:', error);
                showError('Failed to perform search');
                throw error;
            }
        },
        staleTime: 2 * 60 * 1000,      // Results stay fresh for 2 minutes
        gcTime: 10 * 60 * 1000,        // Keep inactive results for 10 minutes
        retry: 1,                       // Only retry once for search queries
        retryDelay: 1000,
        placeholderData: keepPreviousData,  // Keep previous results while fetching new ones
        refetchOnWindowFocus: false,    // Don't refetch on window focus
        refetchOnMount: true,           // Refetch when component mounts
        enabled: !!query               // Only run if there's a query
    });
};
