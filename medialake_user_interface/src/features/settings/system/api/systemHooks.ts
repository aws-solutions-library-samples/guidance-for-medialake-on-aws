import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { QUERY_KEYS } from "@/api/queryKeys";
import {
  SystemSettingsResponse,
  SystemSettingsError,
  SearchProviderCreate,
  SearchProviderUpdate,
} from "../types/system.types";
import { SYSTEM_API } from "./system.endpoints";

export const useSystemSettings = () => {
  const { showError } = useErrorModal();

  return useQuery<SystemSettingsResponse, SystemSettingsError>({
    queryKey: QUERY_KEYS.SYSTEM_SETTINGS.all,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<SystemSettingsResponse>(
          SYSTEM_API.endpoints.GET_SYSTEM_SETTINGS,
          { signal },
        );

        if (!response.data) {
          throw new Error("Invalid system settings response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("System settings fetch error:", error);
        showError("Failed to fetch system settings");
        throw error;
      }
    },
  });
};

export const useSearchProvider = () => {
  const { showError } = useErrorModal();

  return useQuery<SystemSettingsResponse, SystemSettingsError>({
    queryKey: QUERY_KEYS.SYSTEM_SETTINGS.search(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<SystemSettingsResponse>(
          SYSTEM_API.endpoints.GET_SEARCH_PROVIDER,
          { signal },
        );

        if (!response.data) {
          throw new Error("Invalid search provider response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Search provider fetch error:", error);
        showError("Failed to fetch search provider");
        throw error;
      }
    },
  });
};

export const useCreateSearchProvider = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<
    SystemSettingsResponse,
    SystemSettingsError,
    SearchProviderCreate
  >({
    mutationFn: async (provider) => {
      try {
        const response = await apiClient.post<SystemSettingsResponse>(
          SYSTEM_API.endpoints.CREATE_SEARCH_PROVIDER,
          provider,
        );

        return response.data;
      } catch (error) {
        logger.error("Search provider creation error:", error);
        showError("Failed to create search provider");
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SYSTEM_SETTINGS.all,
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SYSTEM_SETTINGS.search(),
      });
    },
  });
};

export const useUpdateSearchProvider = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<
    SystemSettingsResponse,
    SystemSettingsError,
    SearchProviderUpdate
  >({
    mutationFn: async (provider) => {
      try {
        const response = await apiClient.put<SystemSettingsResponse>(
          SYSTEM_API.endpoints.UPDATE_SEARCH_PROVIDER,
          provider,
        );

        return response.data;
      } catch (error) {
        logger.error("Search provider update error:", error);
        showError("Failed to update search provider");
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SYSTEM_SETTINGS.all,
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SYSTEM_SETTINGS.search(),
      });
    },
  });
};
