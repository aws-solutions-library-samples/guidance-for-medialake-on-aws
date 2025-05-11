import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { apiClient } from '@/api/apiClient';
import { API_ENDPOINTS } from '@/api/endpoints';
import { logger } from '@/common/helpers/logger';
import { useErrorModal } from '@/hooks/useErrorModal';
import { QUERY_KEYS } from '@/api/queryKeys';
import axios from 'axios';

interface SearchParams {
    page?: number;
    pageSize?: number;
    isSemantic?: boolean;
    fields?: string[];
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

export interface SearchResponseType {
    status: string;
    message: string;
    data: SearchResponseData | null;
}

export interface SearchError extends Error {
    apiResponse?: SearchResponseType;
}

export const useSearch = (query: string, params?: SearchParams) => {
    const page = params?.page || 1;
    const pageSize = params?.pageSize || 20;
    const isSemantic = params?.isSemantic ?? false;
    const fields = params?.fields || [];
    const { showError } = useErrorModal();

    return useQuery<SearchResponseType, SearchError>({
        queryKey: QUERY_KEYS.SEARCH.list(query, page, pageSize, isSemantic, fields),
        queryFn: async ({ signal }) => {
            try {
                // Build the URL with query parameters
                let url = `${API_ENDPOINTS.SEARCH}?q=${encodeURIComponent(query)}&page=${page}&pageSize=${pageSize}&semantic=${isSemantic}`;
                
                // Add fields parameter if fields are specified
                if (fields.length > 0) {
                    url += `&fields=${encodeURIComponent(fields.join(','))}`;
                }
                
                const response = await apiClient.get<SearchResponseType>(url, { signal });

                // Check if the response status is not a success (2xx)
                if (response.data?.status && !response.data.status.startsWith('2')) {
                    const error = new Error(response.data.message || 'Search request failed') as SearchError;
                    error.apiResponse = response.data;
                    throw error;
                }

                if (!response.data?.data?.results) {
                    throw new Error('Invalid search response structure');
                }

                return response.data;
            } catch (error) {
                logger.error('Search error:', error);
                
                // Handle axios errors
                if (axios.isAxiosError(error) && error.response?.data) {
                    const apiError = new Error(
                        error.response.data.message || 'Search request failed'
                    ) as SearchError;
                    apiError.apiResponse = error.response.data;
                    throw apiError;
                }
                
                // Rethrow the error to be handled by the component
                throw error;
            }
        },
        placeholderData: keepPreviousData,
        enabled: !!query, // Only enable and refetch if there is a query
        staleTime: 1000 * 60, // Cache for 1 minute
        gcTime: 1000 * 60 * 5 // Keep unused data for 5 minutes
    });
};
