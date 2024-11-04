import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { logger } from '../../common/helpers/logger';
import { useErrorModal } from '../../hooks/useErrorModal';
import type { ApiResponse, S3ListObjectsResponse } from '../types/api.types';

// Query configuration defaults
const defaultQueryConfig = {
    staleTime: 30000, // 30 seconds
    retry: 3,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    retryDelay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 30000),
};

interface S3ExplorerParams {
    connectorId: string;
    prefix?: string;
    delimiter?: string;
    continuationToken?: string | null;
}

export const useS3Explorer = ({
    connectorId,
    prefix = '',
    delimiter = '/',
    continuationToken = null,
}: S3ExplorerParams) => {
    const { showError } = useErrorModal();

    return useQuery<ApiResponse<S3ListObjectsResponse>, Error>({
        queryKey: QUERY_KEYS.CONNECTORS.s3.explorer(connectorId, prefix, continuationToken),
        queryFn: async ({ signal }) => {
            try {
                const response = await apiClient.get<ApiResponse<S3ListObjectsResponse>>(
                    `${API_ENDPOINTS.CONNECTORS}/s3/explorer/${connectorId}`,
                    {
                        params: {
                            prefix,
                            delimiter,
                            continuationToken
                        },
                        signal
                    }
                );
                return response.data;
            } catch (error) {
                logger.error('S3 Explorer error:', error);
                showError('Failed to fetch S3 contents');
                throw error;
            }
        },
        enabled: !!connectorId,
        ...defaultQueryConfig,
    });
};
