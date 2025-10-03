import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  integrationsController,
  INTEGRATIONS_QUERY_KEYS,
} from "../api/integrations.controller";
import type {
  Integration,
  IntegrationFormData,
  IntegrationsError,
} from "../types/integrations.types";

export const useIntegrations = () => {
  return useQuery({
    queryKey: INTEGRATIONS_QUERY_KEYS.list(),
    queryFn: () => integrationsController.getIntegrations(),
    retry: (failureCount, error: IntegrationsError) => {
      if (error.status?.toString().startsWith("4")) {
        return false;
      }
      return failureCount < 3;
    },
  });
};

export const useIntegration = (id: string) => {
  return useQuery({
    queryKey: INTEGRATIONS_QUERY_KEYS.detail(id),
    queryFn: () => integrationsController.getIntegration(id),
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: IntegrationFormData) => {
      console.log("[useCreateIntegration] Starting mutation with data:", data);
      return integrationsController
        .createIntegration(data)
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Integration> }) =>
      integrationsController.updateIntegration(id, data),
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: { status: string } }) =>
      integrationsController.updateStatus(id, status),
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

export const useDeleteIntegration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => integrationsController.deleteIntegration(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: INTEGRATIONS_QUERY_KEYS.list(),
      });
    },
  });
};
