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

export interface SearchResult {
    inventoryId: string;
    assetId: string;
    assetType: string;
    createDate: string;
    mainRepresentation: {
        id: string;
        type: string;
        format: string;
        purpose: string;
        storage: {
            storageType: string;
            bucket: string;
            path: string;
            status: string;
            fileSize: number;
            hashValue: string;
        };
        imageSpec?: {
            colorSpace: string | null;
            width: number | null;
            height: number | null;
            dpi: number | null;
        };
    };
    derivedRepresentations: any[];
    metadata: any;
    score: number;
}

export interface SearchResponse {
    status: string;
    message: string;
    data: {
        searchMetadata: {
            totalResults: number;
            page: number;
            pageSize: number;
            searchTerm: string;
            facets: {
                file_types: {
                    doc_count_error_upper_bound: number;
                    sum_other_doc_count: number;
                    buckets: Array<{
                        key: string;
                        doc_count: number;
                    }>;
                };
                asset_types: {
                    doc_count_error_upper_bound: number;
                    sum_other_doc_count: number;
                    buckets: Array<{
                        key: string;
                        doc_count: number;
                    }>;
                };
            };
            suggestions: {
                simple_phrase: Array<{
                    text: string;
                    offset: number;
                    length: number;
                    options: any[];
                }>;
            };
        };
        results: SearchResult[];
    };
}

export const useSearch = (query: string, filters?: SearchFilters) => {
    const { showError } = useErrorModal();

    return useQuery<SearchResponse>({
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

                const response = await apiClient.get<SearchResponse>(`${API_ENDPOINTS.SEARCH}?${params.toString()}`, { signal });
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
