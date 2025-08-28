import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import {
  Environment,
  EnvironmentsResponse,
  EnvironmentResponse,
  EnvironmentError,
  EnvironmentCreate,
  EnvironmentUpdate,
} from "../types/environments.types";
import { ENVIRONMENTS_API } from "./environments.endpoints";

export const useEnvironments = () => {
  const { showError } = useErrorModal();

  return useQuery<EnvironmentsResponse, EnvironmentError>({
    queryKey: ["environments"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<EnvironmentsResponse>(
          ENVIRONMENTS_API.endpoints.GET_ENVIRONMENTS,
          { signal },
        );

        if (!response.data?.data) {
          throw new Error("Invalid environments response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Environments fetch error:", error);
        showError("Failed to fetch environments");
        throw error;
      }
    },
  });
};

export const useEnvironment = (id: string) => {
  const { showError } = useErrorModal();

  return useQuery<EnvironmentResponse, EnvironmentError>({
    queryKey: ["environment", id],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<EnvironmentResponse>(
          ENVIRONMENTS_API.endpoints.GET_ENVIRONMENT(id),
          { signal },
        );

        if (!response.data?.data) {
          throw new Error("Invalid environment response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Environment fetch error:", error);
        showError("Failed to fetch environment");
        throw error;
      }
    },
    enabled: !!id,
  });
};

export const useCreateEnvironment = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async (environment: EnvironmentCreate) => {
      try {
        const response = await apiClient.post<EnvironmentResponse>(
          ENVIRONMENTS_API.endpoints.CREATE_ENVIRONMENT,
          environment,
        );

        return response.data;
      } catch (error) {
        logger.error("Environment creation error:", error);
        showError("Failed to create environment");
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
    },
  });
};

export const useUpdateEnvironment = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async ({
      id,
      environment,
    }: {
      id: string;
      environment: EnvironmentUpdate;
    }) => {
      try {
        const response = await apiClient.put<EnvironmentResponse>(
          ENVIRONMENTS_API.endpoints.UPDATE_ENVIRONMENT(id),
          environment,
        );

        return response.data;
      } catch (error) {
        logger.error("Environment update error:", error);
        showError("Failed to update environment");
        throw error;
      }
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
      queryClient.invalidateQueries({ queryKey: ["environment", id] });
    },
  });
};

export const useDeleteEnvironment = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async (id: string) => {
      try {
        const response = await apiClient.delete<{
          status: string;
          message: string;
        }>(ENVIRONMENTS_API.endpoints.DELETE_ENVIRONMENT(id));

        return response.data;
      } catch (error) {
        logger.error("Environment deletion error:", error);
        showError("Failed to delete environment");
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
    },
  });
};
