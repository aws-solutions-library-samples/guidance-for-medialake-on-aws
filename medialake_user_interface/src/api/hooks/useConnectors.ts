import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient, UseQueryOptions } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';
import { logger } from '../../common/helpers/logger';
import { useErrorModal } from '../../hooks/useErrorModal';
import type {
    S3BucketResponse,
    ConnectorResponse,
    CreateConnectorRequest,
    UpdateConnectorRequest,
    ConnectorListResponse,
    ApiResponse
} from '../types/api.types';

// Query configuration defaults
const defaultQueryConfig = {
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 30 * 60 * 1000, // 30 minutes
    retry: 3,
    retryDelay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 30000),
};

const validateConnectorRequest = (data: any) => {
    if (!data) {
        throw new Error('Connector data is required');
    }
    // Add more validation as needed
};

const validateS3ConnectorRequest = (data: any) => {
    validateConnectorRequest(data);
    // Add S3-specific validation as needed
};

export const useGetS3Buckets = () => {
    const { showError } = useErrorModal();

    return useQuery<S3BucketResponse, Error>({
        queryKey: [QUERY_KEYS.CONNECTORS, 's3'],
        queryFn: async ({ signal }) => {
            try {
                const response = await apiClient.get<S3BucketResponse>(
                    `${API_ENDPOINTS.CONNECTORS}/s3`,
                    { signal }
                );
                return response.data;
            } catch (error) {
                logger.error('Fetch S3 buckets error:', error);
                showError('Failed to fetch S3 buckets');
                throw error;
            }
        },
        ...defaultQueryConfig,
    });
};

export const useGetConnectors = () => {
    const { showError } = useErrorModal();

    return useQuery<ConnectorListResponse, Error>({
        queryKey: [QUERY_KEYS.CONNECTORS],
        queryFn: async ({ signal }) => {
            try {
                const response = await apiClient.get<ConnectorListResponse>(
                    API_ENDPOINTS.CONNECTORS,
                    { signal }
                );
                return response.data;
            } catch (error) {
                logger.error('Fetch connectors error:', error);
                showError('Failed to fetch connectors');
                throw error;
            }
        },
        ...defaultQueryConfig,
    });
};

export const useCreateConnector = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation<ConnectorResponse, Error, CreateConnectorRequest>({
        mutationFn: async (data) => {
            validateConnectorRequest(data);
            const response = await apiClient.post<ConnectorResponse>(
                API_ENDPOINTS.CONNECTORS,
                data
            );
            return response.data;
        },
        onError: (error) => {
            logger.error('Create connector error:', error);
            if (error.message === 'Network Error') {
                showError('Unable to save connector - API is not available');
            } else {
                showError(`Failed to create connector: ${error.message}`);
            }
        },
        onSuccess: (newConnector) => {
            queryClient.setQueryData<ConnectorListResponse>(
                [QUERY_KEYS.CONNECTORS],
                (old) => {
                    if (!old) return {
                        status: 'success',
                        message: 'Connectors retrieved successfully',
                        data: { connectors: [newConnector] }
                    };
                    return {
                        status: old.status,
                        message: old.message,
                        data: {
                            ...old.data,
                            connectors: [...old.data.connectors, newConnector]
                        }
                    };
                }
            );
        },
    });
};

export const useUpdateConnector = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation<
        ConnectorResponse,
        Error,
        { id: string; data: UpdateConnectorRequest }
    >({
        mutationFn: async ({ id, data }) => {
            validateConnectorRequest(data);
            const response = await apiClient.put<ConnectorResponse>(
                `${API_ENDPOINTS.CONNECTORS}/${id}`,
                data
            );
            return response.data;
        },
        onMutate: async ({ id, data }) => {
            await queryClient.cancelQueries({ queryKey: [QUERY_KEYS.CONNECTORS] });

            const previousConnectors = queryClient.getQueryData<ConnectorListResponse>(
                [QUERY_KEYS.CONNECTORS]
            );

            queryClient.setQueryData<ConnectorListResponse>(
                [QUERY_KEYS.CONNECTORS],
                (old) => {
                    if (!old) return previousConnectors;
                    return {
                        status: old.status,
                        message: old.message,
                        data: {
                            ...old.data,
                            connectors: old.data.connectors.map(connector =>
                                connector.id === id
                                    ? { ...connector, ...data }
                                    : connector
                            )
                        }
                    };
                }
            );

            return { previousConnectors };
        },
        onError: (error, variables, context: { previousConnectors?: ConnectorListResponse }) => {
            if (context?.previousConnectors) {
                queryClient.setQueryData(
                    [QUERY_KEYS.CONNECTORS],
                    context.previousConnectors
                );
            }
            logger.error('Update connector error:', error);
            if (error.message === 'Network Error') {
                showError('Unable to save connector - API is not available');
            } else {
                showError(`Failed to update connector: ${error.message}`);
            }
        }
    });
};

export const useDeleteConnector = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation({
        mutationFn: async (id: string) => {
            try {
                const response = await apiClient.delete<ApiResponse<void>>(
                    `${API_ENDPOINTS.CONNECTORS}/${id}`
                );
                return response.data;
            } catch (error) {
                logger.error('Delete connector error:', error);
                showError('Failed to delete connector');
                throw error;
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.CONNECTORS] });
        },
    });
};

export const useCreateS3Connector = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    useEffect(() => {
        queryClient.prefetchQuery({
            queryKey: [QUERY_KEYS.CONNECTORS, 's3'],
            queryFn: async () => {
                const response = await apiClient.get<S3BucketResponse>(
                    `${API_ENDPOINTS.CONNECTORS}/s3`
                );
                return response.data;
            },
        });
    }, [queryClient]);

    return useMutation<ConnectorResponse, Error, CreateConnectorRequest>({
        mutationFn: async (data) => {
            validateS3ConnectorRequest(data);
            const response = await apiClient.post<ConnectorResponse>(
                `${API_ENDPOINTS.CONNECTORS}/s3`,
                data
            );
            return response.data;
        },
        onError: (error) => {
            logger.error('Create S3 connector error:', error);
            if (error.message === 'Network Error') {
                showError('Unable to save connector - API is not available');
            } else {
                showError(`Failed to create S3 connector: ${error.message}`);
            }
        },
        onSuccess: (newConnector) => {
            queryClient.setQueryData<ConnectorListResponse>(
                [QUERY_KEYS.CONNECTORS],
                (old) => {
                    if (!old) return {
                        status: 'success',
                        message: 'Connectors retrieved successfully',
                        data: { connectors: [newConnector] }
                    };
                    return {
                        status: old.status,
                        message: old.message,
                        data: {
                            ...old.data,
                            connectors: [...old.data.connectors, newConnector]
                        }
                    };
                }
            );
        },
    });
};

export const useCreateGCSConnector = () => {
    const { showError } = useErrorModal();

    return useMutation<ConnectorResponse, Error, CreateConnectorRequest>({
        mutationFn: async (data) => {
            const response = await apiClient.post<ConnectorResponse>(`${API_ENDPOINTS.CONNECTORS}/gcs`, data);
            return response.data;
        },
        onError: (error) => {
            logger.error('Create GCS connector error:', error);
            if (error.message === 'Network Error') {
                showError('Unable to save connector - API is not available');
            } else {
                showError(`Failed to create GCS connector: ${error.message}`);
            }
        },
    });
};
