import { useQuery, useMutation, QueryClient } from "@tanstack/react-query";
import { environmentsQueryClient } from "../api/environmentsQueryClient";
import { apiClient } from "@/api/apiClient";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { ENVIRONMENTS_API } from "../api/environments.endpoints";
import type {
  Environment,
  EnvironmentsResponse,
  EnvironmentResponse,
  EnvironmentCreate,
  EnvironmentUpdate,
  EnvironmentError,
} from "../types/environments.types";

const ENVIRONMENTS_CACHE_KEY = "environments";

// Create a wrapper function to use the environments query client
const useEnvironmentsQueryWithClient = <T>(
  queryFn: (client: QueryClient) => T,
): T => {
  return queryFn(environmentsQueryClient);
};

export const useEnvironmentsQuery = () => {
  const { showError } = useErrorModal();

  return useEnvironmentsQueryWithClient((queryClient) =>
    useQuery<EnvironmentsResponse, EnvironmentError>({
      queryKey: [ENVIRONMENTS_CACHE_KEY],
      queryFn: async ({ signal }) => {
        try {
          const response = await apiClient.get<EnvironmentsResponse>(
            ENVIRONMENTS_API.endpoints.GET_ENVIRONMENTS,
            { signal },
          );
          return response.data;
        } catch (error) {
          logger.error("Environments fetch error:", error);
          showError("Failed to fetch environments");
          throw error;
        }
      },
    }),
  );
};

export const useCreateEnvironmentMutation = () => {
  const { showError } = useErrorModal();

  return useEnvironmentsQueryWithClient((queryClient) =>
    useMutation({
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
        queryClient.invalidateQueries({ queryKey: [ENVIRONMENTS_CACHE_KEY] });
      },
    }),
  );
};

export const useUpdateEnvironmentMutation = () => {
  const { showError } = useErrorModal();

  return useEnvironmentsQueryWithClient((queryClient) =>
    useMutation({
      mutationFn: async ({
        id,
        data,
      }: {
        id: string;
        data: EnvironmentUpdate;
      }) => {
        try {
          const response = await apiClient.put<EnvironmentResponse>(
            ENVIRONMENTS_API.endpoints.UPDATE_ENVIRONMENT(id),
            data,
          );
          return response.data;
        } catch (error) {
          logger.error("Environment update error:", error);
          showError("Failed to update environment");
          throw error;
        }
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: [ENVIRONMENTS_CACHE_KEY] });
      },
    }),
  );
};

export const useDeleteEnvironmentMutation = () => {
  const { showError } = useErrorModal();

  return useEnvironmentsQueryWithClient((queryClient) =>
    useMutation({
      mutationFn: async (id: string) => {
        try {
          const response = await apiClient.delete(
            ENVIRONMENTS_API.endpoints.DELETE_ENVIRONMENT(id),
          );
          return response.data;
        } catch (error) {
          logger.error("Environment deletion error:", error);
          showError("Failed to delete environment");
          throw error;
        }
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: [ENVIRONMENTS_CACHE_KEY] });
      },
    }),
  );
};
