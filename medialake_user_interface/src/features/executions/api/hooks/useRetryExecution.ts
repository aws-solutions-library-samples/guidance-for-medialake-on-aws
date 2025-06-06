import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/apiClient';
import { API_ENDPOINTS } from '@/api/endpoints';
import { QUERY_KEYS } from '@/api/queryKeys';
import { logger } from '@/common/helpers/logger';
import { useErrorModal } from '@/hooks/useErrorModal';
import { useSnackbar } from '@/hooks/useSnackbar';

interface RetryFromCurrentResponse {
    status: string;
    message: string;
    redrive_date?: string;
}

interface RetryFromStartResponse {
    status: string;
    message: string;
    new_execution_arn?: string;
}

interface RetryError {
    status: string;
    message: string;
    suggestedAction?: 'USE_RETRY_FROM_START' | 'CONTACT_SUPPORT';
}

export const useRetryFromCurrent = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();
    const { showSnackbar } = useSnackbar();

    return useMutation({
        mutationFn: async (executionId: string): Promise<RetryFromCurrentResponse> => {
            try {
                const response = await apiClient.post<RetryFromCurrentResponse>(
                    API_ENDPOINTS.PIPELINE_EXECUTION_RETRY.FROM_CURRENT(executionId)
                );
                return response.data;
            } catch (error: any) {
                logger.error('Retry from current error:', error);
                
                // Handle specific retry errors
                if (error.response?.status === 400) {
                    const errorData = error.response.data as RetryError;
                    if (errorData.suggestedAction === 'USE_RETRY_FROM_START') {
                        throw new Error(`${errorData.message}. Try "Retry from Start" instead.`);
                    }
                    throw new Error(errorData.message);
                } else if (error.response?.status === 404) {
                    throw new Error('Execution not found');
                } else if (error.response?.status === 500) {
                    throw new Error('Failed to retry execution. Please try again later.');
                }
                
                throw new Error('Failed to retry execution from current position');
            }
        },
        onSuccess: (data, executionId) => {
            logger.info('Successfully redrove execution from current position:', { executionId, data });
            
            // Show success notification
            showSnackbar({
                message: 'Execution successfully restarted from current position',
                severity: 'success'
            });
            
            // Invalidate and refetch executions list
            queryClient.invalidateQueries({
                queryKey: [QUERY_KEYS.PIPELINE_EXECUTIONS.all]
            });
        },
        onError: (error: Error) => {
            logger.error('Failed to retry execution from current position:', error);
            showError(error.message);
        }
    });
};

export const useRetryFromStart = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();
    const { showSnackbar } = useSnackbar();

    return useMutation({
        mutationFn: async (executionId: string): Promise<RetryFromStartResponse> => {
            try {
                const response = await apiClient.post<RetryFromStartResponse>(
                    API_ENDPOINTS.PIPELINE_EXECUTION_RETRY.FROM_START(executionId)
                );
                return response.data;
            } catch (error: any) {
                logger.error('Retry from start error:', error);
                
                // Handle specific retry errors
                if (error.response?.status === 404) {
                    throw new Error('Execution not found');
                } else if (error.response?.status === 500) {
                    const errorData = error.response.data as RetryError;
                    throw new Error(errorData.message || 'Failed to start new execution. Please try again later.');
                }
                
                throw new Error('Failed to retry execution from start');
            }
        },
        onSuccess: (data, executionId) => {
            logger.info('Successfully started new execution from start:', { executionId, data });
            
            // Show success notification
            showSnackbar({
                message: 'New execution started successfully from beginning',
                severity: 'success'
            });
            
            // Invalidate and refetch executions list
            queryClient.invalidateQueries({
                queryKey: [QUERY_KEYS.PIPELINE_EXECUTIONS.all]
            });
        },
        onError: (error: Error) => {
            logger.error('Failed to retry execution from start:', error);
            showError(error.message);
        }
    });
};

// Legacy retry hook for backward compatibility
export const useRetryExecution = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();
    const { showSnackbar } = useSnackbar();

    return useMutation({
        mutationFn: async (executionId: string): Promise<{ status: string; message: string }> => {
            try {
                const response = await apiClient.post<{ status: string; message: string }>(
                    API_ENDPOINTS.PIPELINE_EXECUTION_RETRY.LEGACY(executionId)
                );
                return response.data;
            } catch (error: any) {
                logger.error('Legacy retry error:', error);
                
                if (error.response?.status === 404) {
                    throw new Error('Execution not found');
                } else if (error.response?.status === 500) {
                    throw new Error('Failed to retry execution. Please try again later.');
                }
                
                throw new Error('Failed to retry execution');
            }
        },
        onSuccess: (data, executionId) => {
            logger.info('Successfully retried execution (legacy):', { executionId, data });
            
            // Show success notification
            showSnackbar({
                message: 'Execution retried successfully',
                severity: 'success'
            });
            
            // Invalidate and refetch executions list
            queryClient.invalidateQueries({
                queryKey: [QUERY_KEYS.PIPELINE_EXECUTIONS.all]
            });
        },
        onError: (error: Error) => {
            logger.error('Failed to retry execution (legacy):', error);
            showError(error.message);
        }
    });
};