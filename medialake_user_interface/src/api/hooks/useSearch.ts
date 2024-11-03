import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { logger } from '../../common/helpers/logger';
import { useErrorModal } from '../../hooks/useErrorModal';

export interface SearchFilters {
    creationDate?: {
        before?: string;
        after?: string;
    };
    media?: {
        video?: string[];
        images?: string[];
        audio?: string[];
    };
    metadata?: {
        title?: string[];
        rights?: string[];
    };
}

export const useSearch = (query: string, filters?: SearchFilters) => {
    const { showError } = useErrorModal();

    return useQuery({
        queryKey: [...QUERY_KEYS.SEARCH.all, query, filters],
        queryFn: async ({ signal }) => {
            try {
                const params = new URLSearchParams();
                params.append('q', query);

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

                const response = await apiClient.get(`${API_ENDPOINTS.SEARCH}?${params.toString()}`, { signal });
                return response.data;
            } catch (error) {
                logger.error('Search error:', error);
                showError('Failed to perform search');
                throw error;
            }
        },
        enabled: !!query,
    });
};
