import { useMutation, useQuery } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";
import type {
  Portal,
  PortalListItem,
  PortalListResponse,
  PortalResponse,
  PortalTokenListResponse,
  PortalTokenResponse,
  CreatePortalRequest,
  UpdatePortalRequest,
  GenerateTokenRequest,
} from "@/api/types/api.types";

/** Extract a normalized error message from a 409 response, or return null. */
function extract409Message(error: any): string | null {
  if (error?.response?.status !== 409) return null;
  const body = error?.response?.data;
  return body?.error?.message || body?.message || "Slug already exists";
}

export const useGetPortals = () => {
  const { showError } = useErrorModal();

  return useQuery<PortalListResponse, Error>({
    queryKey: QUERY_KEYS.PORTALS.all,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalListResponse>(API_ENDPOINTS.PORTALS.BASE, {
          signal,
          skipAccessDeniedRedirect: true,
        } as any);
        return response.data;
      } catch (error: any) {
        if (error?.response?.status === 403) {
          logger.warn("No permission for portals, returning empty list");
          return { success: true, data: [] } as PortalListResponse;
        }
        logger.error("Fetch portals error:", error);
        showError("Failed to fetch portals");
        throw error;
      }
    },
  });
};

export const useGetPortal = (id: string) => {
  const { showError } = useErrorModal();

  return useQuery<PortalResponse, Error>({
    queryKey: QUERY_KEYS.PORTALS.detail(id),
    enabled: !!id,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalResponse>(API_ENDPOINTS.PORTALS.GET(id), {
          signal,
        });
        return response.data;
      } catch (error: any) {
        logger.error("Fetch portal error:", error);
        showError("Failed to fetch portal");
        throw error;
      }
    },
  });
};

export const useCreatePortal = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalResponse, Error, CreatePortalRequest>({
    mutationFn: async (data) => {
      try {
        const response = await apiClient.post<PortalResponse>(API_ENDPOINTS.PORTALS.BASE, data);
        return response.data;
      } catch (error: any) {
        const conflictMsg = extract409Message(error);
        if (conflictMsg) throw new Error(conflictMsg);
        throw error;
      }
    },
    onError: (error: any) => {
      // 409 errors are already mapped in mutationFn; don't show modal for those
      if (error?.message?.toLowerCase().includes("slug")) return;
      logger.error("Create portal error:", error);
      showError(`Failed to create portal: ${error.message}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.all });
    },
  });
};

export const useUpdatePortal = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalResponse, Error, { id: string; data: UpdatePortalRequest }>({
    mutationFn: async ({ id, data }) => {
      try {
        const response = await apiClient.put<PortalResponse>(
          API_ENDPOINTS.PORTALS.UPDATE(id),
          data
        );
        return response.data;
      } catch (error: any) {
        const conflictMsg = extract409Message(error);
        if (conflictMsg) throw new Error(conflictMsg);
        throw error;
      }
    },
    onError: (error: any) => {
      if (error?.message?.toLowerCase().includes("slug")) return;
      logger.error("Update portal error:", error);
      showError(`Failed to update portal: ${error.message}`);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.all });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.detail(variables.id) });
    },
  });
};

export const useDeletePortal = () => {
  const { showError } = useErrorModal();

  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(API_ENDPOINTS.PORTALS.DELETE(id));
    },
    onError: (error) => {
      logger.error("Delete portal error:", error);
      showError("Failed to delete portal");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.all });
    },
  });
};

export const useTogglePortalActive = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalResponse, Error, { id: string; isActive: boolean }>({
    mutationFn: async ({ id, isActive }) => {
      const response = await apiClient.put<PortalResponse>(API_ENDPOINTS.PORTALS.UPDATE(id), {
        isActive,
      });
      return response.data;
    },
    onMutate: async ({ id, isActive }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PORTALS.all });
      const previous = queryClient.getQueryData<PortalListResponse>(QUERY_KEYS.PORTALS.all);

      queryClient.setQueryData<PortalListResponse>(QUERY_KEYS.PORTALS.all, (old) => {
        if (!old) return previous;
        return {
          ...old,
          data: old.data.map((p) => (p.portalId === id ? { ...p, isActive } : p)),
        };
      });

      return { previous };
    },
    onError: (error, _vars, context: any) => {
      if (context?.previous) {
        queryClient.setQueryData(QUERY_KEYS.PORTALS.all, context.previous);
      }
      logger.error("Toggle portal error:", error);
      showError("Failed to toggle portal status");
    },
  });
};

export const useUploadPortalLogo = () => {
  const { showError } = useErrorModal();

  return useMutation<any, Error, { id: string; base64Image: string; contentType: string }>({
    mutationFn: async ({ id, base64Image, contentType }) => {
      const response = await apiClient.post(API_ENDPOINTS.PORTALS.LOGO(id), {
        data: base64Image,
        contentType,
      });
      return response.data;
    },
    onError: (error) => {
      logger.error("Upload portal logo error:", error);
      showError("Failed to upload logo");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.all });
    },
  });
};

/**
 * Mutation for uploading a portal banner image.
 *
 * POSTs a base64-encoded payload to `/settings/portals/:id/banner`. Mirrors
 * the shape of {@link useUploadPortalLogo} so the visual editor's
 * `BrandingSection` can share a common `{ id, base64Image, contentType }`
 * contract across both uploaders.
 *
 * The backend stores the image in S3 and returns the resulting S3 key. The
 * caller (the editor's `BrandingSection`, task 3.8) stashes that key in
 * `appearance.branding.bannerS3Key` via `updateBranding({ bannerS3Key })`.
 * The public portal read path resolves the key to a CDN URL server-side,
 * populating the transient `bannerUrl` on the response (Requirement 7.7).
 */
export const useUploadPortalBanner = () => {
  const { showError } = useErrorModal();

  return useMutation<any, Error, { id: string; base64Image: string; contentType: string }>({
    mutationFn: async ({ id, base64Image, contentType }) => {
      const response = await apiClient.post(API_ENDPOINTS.PORTALS.BANNER(id), {
        data: base64Image,
        contentType,
      });
      return response.data;
    },
    onError: (error) => {
      logger.error("Upload portal banner error:", error);
      showError("Failed to upload banner");
    },
    onSuccess: () => {
      // The banner key is embedded in the portal record, so invalidating the
      // portals list keeps the list view in sync once the backend rolls out.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.all });
    },
  });
};

/**
 * Mutation for uploading a portal favicon image.
 *
 * POSTs a base64-encoded payload to `/settings/portals/:id/favicon`. Mirrors
 * the shape of {@link useUploadPortalBanner} so the visual editor's
 * `BrandingSection` can share a common `{ id, base64Image, contentType }`
 * contract across all uploaders.
 */
export const useUploadPortalFavicon = () => {
  const { showError } = useErrorModal();

  return useMutation<any, Error, { id: string; base64Image: string; contentType: string }>({
    mutationFn: async ({ id, base64Image, contentType }) => {
      const response = await apiClient.post(API_ENDPOINTS.PORTALS.FAVICON(id), {
        data: base64Image,
        contentType,
      });
      return response.data;
    },
    onError: (error) => {
      logger.error("Upload portal favicon error:", error);
      showError("Failed to upload favicon");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.all });
    },
  });
};

export const useGetPortalTokens = (portalId: string) => {
  const { showError } = useErrorModal();

  return useQuery<PortalTokenListResponse, Error>({
    queryKey: QUERY_KEYS.PORTALS.tokens(portalId),
    enabled: !!portalId,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<PortalTokenListResponse>(
          API_ENDPOINTS.PORTALS.TOKENS(portalId),
          { signal }
        );
        return response.data;
      } catch (error: any) {
        logger.error("Fetch portal tokens error:", error);
        showError("Failed to fetch tokens");
        throw error;
      }
    },
  });
};

export const useGeneratePortalToken = () => {
  const { showError } = useErrorModal();

  return useMutation<PortalTokenResponse, Error, { portalId: string; data: GenerateTokenRequest }>({
    mutationFn: async ({ portalId, data }) => {
      const response = await apiClient.post<PortalTokenResponse>(
        API_ENDPOINTS.PORTALS.TOKENS(portalId),
        data
      );
      return response.data;
    },
    onError: (error) => {
      logger.error("Generate token error:", error);
      showError("Failed to generate token");
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.tokens(variables.portalId) });
    },
  });
};

export const useRevokePortalToken = () => {
  const { showError } = useErrorModal();

  return useMutation<void, Error, { portalId: string; tokenId: string }>({
    mutationFn: async ({ portalId, tokenId }) => {
      await apiClient.delete(API_ENDPOINTS.PORTALS.TOKEN_DELETE(portalId, tokenId));
    },
    onError: (error) => {
      logger.error("Revoke token error:", error);
      showError("Failed to revoke token");
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PORTALS.tokens(variables.portalId) });
    },
  });
};
