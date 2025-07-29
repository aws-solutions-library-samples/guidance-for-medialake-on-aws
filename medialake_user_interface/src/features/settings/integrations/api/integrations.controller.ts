import { useQuery, useMutation } from "@tanstack/react-query";
import { IntegrationsService } from "./integrations.service";
import { INTEGRATIONS_API } from "./integrations.endpoints";
import type {
  IntegrationFormData,
  IntegrationsResponse,
  IntegrationsError,
  Integration,
  CreateIntegrationDto,
  UpdateIntegrationDto,
} from "../types/integrations.types";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";

const transformFormDataToDto = (formData: IntegrationFormData) => {
  return {
    nodeId: formData.nodeId,
    description: formData.description || "",
    auth: formData.auth,
  };
};

export const INTEGRATIONS_QUERY_KEYS = {
  all: ["integrations"] as const,
  list: () => [...INTEGRATIONS_QUERY_KEYS.all, "list"] as const,
  detail: (id: string) =>
    [...INTEGRATIONS_QUERY_KEYS.all, "detail", id] as const,
  status: (id: string) =>
    [...INTEGRATIONS_QUERY_KEYS.all, "status", id] as const,
};

export const useGetIntegrations = () => {
  return useQuery({
    queryKey: INTEGRATIONS_QUERY_KEYS.list(),
    queryFn: () => IntegrationsService.getIntegrations(),
    retry: (failureCount, error: IntegrationsError) => {
      if (error.status?.toString().startsWith("4")) {
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
      if (error.status?.toString().startsWith("4")) {
        return false;
      }
      return failureCount < 3;
    },
  });
};

export const useCreateIntegration = () => {
  return useMutation({
    mutationFn: (data: IntegrationFormData) => {
      console.log(
        "[useCreateIntegration] Starting mutation with form data:",
        data,
      );
      const dto = transformFormDataToDto(data);
      console.log("[useCreateIntegration] Transformed to DTO:", dto);
      return IntegrationsService.createIntegration(dto)
        .then((result) => {
          console.log(
            "[useCreateIntegration] Mutation completed successfully:",
            result,
          );
          return result;
        })
        .catch((error) => {
          console.error("[useCreateIntegration] Mutation failed:", error);
          throw error;
        });
    },
    onSuccess: () => {
      console.log("[useCreateIntegration] Running onSuccess callback");
      queryClient.invalidateQueries({
        queryKey: INTEGRATIONS_QUERY_KEYS.list(),
      });
    },
    onError: (error) => {
      console.error("[useCreateIntegration] Mutation error:", error);
    },
  });
};

export const useUpdateIntegration = () => {
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: IntegrationFormData }) => {
      const dto: UpdateIntegrationDto = {
        description: data.description || "",
        auth: data.auth,
      };
      return IntegrationsService.updateIntegration(id, dto);
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: INTEGRATIONS_QUERY_KEYS.detail(id),
      });
      queryClient.invalidateQueries({
        queryKey: INTEGRATIONS_QUERY_KEYS.list(),
      });
    },
  });
};

export const useUpdateIntegrationStatus = () => {
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: { status: string } }) =>
      IntegrationsService.updateStatus(id, status),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({
        queryKey: INTEGRATIONS_QUERY_KEYS.detail(id),
      });
      queryClient.invalidateQueries({
        queryKey: INTEGRATIONS_QUERY_KEYS.list(),
      });
    },
  });
};

export const integrationsController = {
  getIntegrations: async (): Promise<IntegrationsResponse> => {
    const response = await apiClient.get<IntegrationsResponse>(
      INTEGRATIONS_API.endpoints.GET_INTEGRATIONS,
    );
    return response.data;
  },

  getIntegration: async (id: string): Promise<Integration> => {
    const response = await apiClient.get<Integration>(
      INTEGRATIONS_API.endpoints.GET_INTEGRATION(id),
    );
    return response.data;
  },

  createIntegration: async (
    data: IntegrationFormData,
  ): Promise<Integration> => {
    const response = await apiClient.post<Integration>(
      INTEGRATIONS_API.endpoints.CREATE_INTEGRATION,
      data,
    );
    return response.data;
  },

  updateIntegration: async (
    id: string,
    data: Partial<Integration>,
  ): Promise<Integration> => {
    const response = await apiClient.put<Integration>(
      INTEGRATIONS_API.endpoints.UPDATE_INTEGRATION(id),
      data,
    );
    return response.data;
  },

  updateStatus: async (
    id: string,
    status: { status: string },
  ): Promise<Integration> => {
    const response = await apiClient.patch<Integration>(
      INTEGRATIONS_API.endpoints.UPDATE_STATUS(id),
      status,
    );
    return response.data;
  },

  deleteIntegration: async (id: string): Promise<void> => {
    await apiClient.delete(INTEGRATIONS_API.endpoints.DELETE_INTEGRATION(id));
  },
};
