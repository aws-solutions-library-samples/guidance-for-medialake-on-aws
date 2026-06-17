import { useMutation, useQuery } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";
import type {
  PortalTemplateListResponse,
  PortalTemplateResponse,
  CreatePortalTemplateRequest,
  UpdatePortalTemplateRequest,
} from "@/api/types/api.types";

/**
 * React-query hooks for portal Templates (`/settings/portal-templates`).
 *
 * Mirrors the query/mutation/invalidation patterns in `usePortals.ts`: the
 * list query falls back to an empty list on 403 (no permission), and every
 * create/update/delete invalidates the templates list (plus the specific
 * detail on update).
 */

export const useListTemplates = () => {
  const { showError } = useErrorModal();

  return useQuery<PortalTemplateListResponse, Error>({
    queryKey: QUERY_KEYS.PORTAL_TEMPLATES.all,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalTemplateListResponse>(
          API_ENDPOINTS.PORTAL_TEMPLATES.BASE,
          {
            signal,
            skipAccessDeniedRedirect: true,
          } as any
        );
        return response.data;
      } catch (error: any) {
        if (error?.response?.status === 403) {
          logger.warn("No permission for portal templates, returning empty list");
          return { success: true, data: [] } as PortalTemplateListResponse;
        }
        logger.error("Fetch portal templates error:", error);
        showError("Failed to fetch templates");
        throw error;
      }
    },
  });
};

export const useGetTemplate = (id: string) => {
  const { showError } = useErrorModal();

  return useQuery<PortalTemplateResponse, Error>({
    queryKey: QUERY_KEYS.PORTAL_TEMPLATES.detail(id),
    enabled: !!id,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalTemplateResponse>(
          API_ENDPOINTS.PORTAL_TEMPLATES.GET(id),
          { signal }
        );
        return response.data;
      } catch (error: any) {
        logger.error("Fetch portal template error:", error);
        showError("Failed to fetch template");
        throw error;
      }
    },
  });
};

export const useCreateTemplate = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalTemplateResponse, Error, CreatePortalTemplateRequest>({
    mutationFn: async (data) => {
      const response = await apiClient.post<PortalTemplateResponse>(
        API_ENDPOINTS.PORTAL_TEMPLATES.BASE,
        data
      );
      return response.data;
    },
    onError: (error: any) => {
      logger.error("Create template error:", error);
      showError(`Failed to create template: ${error.message}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_TEMPLATES.all });
    },
  });
};

export const useUpdateTemplate = () => {
  const { showError } = useErrorModal();

  return useMutation<
    PortalTemplateResponse,
    Error,
    { id: string; data: UpdatePortalTemplateRequest }
  >({
    mutationFn: async ({ id, data }) => {
      const response = await apiClient.put<PortalTemplateResponse>(
        API_ENDPOINTS.PORTAL_TEMPLATES.UPDATE(id),
        data
      );
      return response.data;
    },
    onError: (error: any) => {
      logger.error("Update template error:", error);
      showError(`Failed to update template: ${error.message}`);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_TEMPLATES.all });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.PORTAL_TEMPLATES.detail(variables.id),
      });
    },
  });
};

export const useDeleteTemplate = () => {
  const { showError } = useErrorModal();

  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(API_ENDPOINTS.PORTAL_TEMPLATES.DELETE(id));
    },
    onError: (error) => {
      logger.error("Delete template error:", error);
      showError("Failed to delete template");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTAL_TEMPLATES.all });
    },
  });
};
