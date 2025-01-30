import { useQuery, useMutation } from '@tanstack/react-query';
import { IntegrationsService } from './integrations.service';
import type {
    IntegrationFormData,
    IntegrationsResponse,
    IntegrationsError,
    Integration,
    CreateIntegrationDto
} from '../types/integrations.types';
import queryClient from '@/api/queryClient';
import { apiClient } from '@/api/apiClient';

const transformFormDataToDto = (formData: IntegrationFormData): CreateIntegrationDto => {
    const now = new Date().toISOString();
    return {
        nodeId: formData.nodeId,
        integrationType: formData.nodeId.replace('node-', '').replace('-api', ''),
        description: formData.description,
        environmentId: formData.environmentId,
        integrationEnabled: true,
        createdDate: now,
        modifiedDate: now,
        auth: formData.auth
    };
};

export const INTEGRATIONS_QUERY_KEYS = {
    all: ['integrations'] as const,
    list: () => [...INTEGRATIONS_QUERY_KEYS.all, 'list'] as const,
    detail: (id: string) => [...INTEGRATIONS_QUERY_KEYS.all, 'detail', id] as const,
    status: (id: string) => [...INTEGRATIONS_QUERY_KEYS.all, 'status', id] as const
};

export const useGetIntegrations = () => {
    return useQuery({
        queryKey: INTEGRATIONS_QUERY_KEYS.list(),
        queryFn: () => IntegrationsService.getIntegrations(),
        retry: (failureCount, error: IntegrationsError) => {
            if (error.status?.toString().startsWith('4')) {
                return false;
            }
            return failureCount < 3;
        },
    });
};

export const useGetIntegration = (id: string) => {
    return useQuery({
        queryKey: INTEGRATIONS_QUERY_KEYS.detail(id),
        queryFn: () => IntegrationsService.getIntegration(id),
        enabled: !!id,
        retry: (failureCount, error: IntegrationsError) => {
            if (error.status?.toString().startsWith('4')) {
                return false;
            }
            return failureCount < 3;
        },
    });
};

export const useCreateIntegration = () => {
    return useMutation({
        mutationFn: (data: IntegrationFormData) => {
            console.log('[useCreateIntegration] Starting mutation with form data:', data);
            const dto = transformFormDataToDto(data);
            console.log('[useCreateIntegration] Transformed to DTO:', dto);
            return IntegrationsService.createIntegration(dto).then(result => {
                console.log('[useCreateIntegration] Mutation completed successfully:', result);
                return result;
            }).catch(error => {
                console.error('[useCreateIntegration] Mutation failed:', error);
                throw error;
            });
        },
        onSuccess: () => {
            console.log('[useCreateIntegration] Running onSuccess callback');
            queryClient.invalidateQueries({ queryKey: INTEGRATIONS_QUERY_KEYS.list() });
        },
        onError: (error) => {
            console.error('[useCreateIntegration] Mutation error:', error);
        }
    });
};

export const useUpdateIntegration = () => {
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: IntegrationFormData }) => {
            const dto = transformFormDataToDto(data);
            return IntegrationsService.updateIntegration(id, dto);
        },
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: INTEGRATIONS_QUERY_KEYS.detail(id) });
            queryClient.invalidateQueries({ queryKey: INTEGRATIONS_QUERY_KEYS.list() });
        },
    });
};

export const useUpdateIntegrationStatus = () => {
    return useMutation({
        mutationFn: ({ id, status }: { id: string; status: { status: string } }) =>
            IntegrationsService.updateStatus(id, status),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: INTEGRATIONS_QUERY_KEYS.detail(id) });
            queryClient.invalidateQueries({ queryKey: INTEGRATIONS_QUERY_KEYS.list() });
        },
    });
};

export const integrationsController = {
    getIntegrations: async (): Promise<IntegrationsResponse> => {
        const response = await apiClient.get<IntegrationsResponse>('/integrations');
        return response.data;
    },

    getIntegration: async (id: string): Promise<Integration> => {
        const response = await apiClient.get<Integration>(`/integrations/${id}`);
        return response.data;
    },

    createIntegration: async (data: IntegrationFormData): Promise<Integration> => {
        const response = await apiClient.post<Integration>('/integrations', data);
        return response.data;
    },

    updateIntegration: async (id: string, data: Partial<Integration>): Promise<Integration> => {
        const response = await apiClient.put<Integration>(`/integrations/${id}`, data);
        return response.data;
    },

    updateStatus: async (id: string, status: { status: string }): Promise<Integration> => {
        const response = await apiClient.patch<Integration>(`/integrations/${id}/status`, status);
        return response.data;
    },

    deleteIntegration: async (id: string): Promise<void> => {
        await apiClient.delete(`/integrations/${id}`);
    }
};