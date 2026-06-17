import { useMutation, useQuery } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";
import type {
  PortalThemeListResponse,
  PortalThemeResponse,
  CreatePortalThemeRequest,
  UpdatePortalThemeRequest,
} from "@/api/types/api.types";

/**
 * React-query hooks for portal appearance Themes (`/settings/portal-themes`).
 *
 * Mirrors the query/mutation/invalidation patterns in `usePortals.ts`: the
 * list query falls back to an empty list on 403 (no permission), and every
 * create/update/delete invalidates the themes list (plus the specific detail
 * on update).
 */

export const useListThemes = () => {
  const { showError } = useErrorModal();

  return useQuery<PortalThemeListResponse, Error>({
    queryKey: QUERY_KEYS.PORTAL_THEMES.all,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalThemeListResponse>(
          API_ENDPOINTS.PORTAL_THEMES.BASE,
          {
            signal,
            skipAccessDeniedRedirect: true,
          } as any
        );
        return response.data;
      } catch (error: any) {
        if (error?.response?.status === 403) {
          logger.warn("No permission for portal themes, returning empty list");
          return { success: true, data: [] } as PortalThemeListResponse;
        }
        logger.error("Fetch portal themes error:", error);
        showError("Failed to fetch themes");
        throw error;
      }
    },
  });
};

export const useGetTheme = (id: string) => {
  const { showError } = useErrorModal();

  return useQuery<PortalThemeResponse, Error>({
    queryKey: QUERY_KEYS.PORTAL_THEMES.detail(id),
    enabled: !!id,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalThemeResponse>(
          API_ENDPOINTS.PORTAL_THEMES.GET(id),
          { signal }
        );
        return response.data;
      } catch (error: any) {
        logger.error("Fetch portal theme error:", error);
        showError("Failed to fetch theme");
        throw error;
      }
    },
  });
};

export const useCreateTheme = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalThemeResponse, Error, CreatePortalThemeRequest>({
    mutationFn: async (data) => {
      const response = await apiClient.post<PortalThemeResponse>(
        API_ENDPOINTS.PORTAL_THEMES.BASE,
        data
      );
      return response.data;
    },
    onError: (error: any) => {
      logger.error("Create theme error:", error);
      showError(`Failed to create theme: ${error.message}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_THEMES.all });
    },
  });
};

export const useUpdateTheme = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalThemeResponse, Error, { id: string; data: UpdatePortalThemeRequest }>({
    mutationFn: async ({ id, data }) => {
      const response = await apiClient.put<PortalThemeResponse>(
        API_ENDPOINTS.PORTAL_THEMES.UPDATE(id),
        data
      );
      return response.data;
    },
    onError: (error: any) => {
      logger.error("Update theme error:", error);
      showError(`Failed to update theme: ${error.message}`);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_THEMES.all });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_THEMES.detail(variables.id) });
    },
  });
};

export const useDeleteTheme = () => {
  const { showError } = useErrorModal();

  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(API_ENDPOINTS.PORTAL_THEMES.DELETE(id));
    },
    onError: (error) => {
      logger.error("Delete theme error:", error);
      showError("Failed to delete theme");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_THEMES.all });
    },
  });
};
