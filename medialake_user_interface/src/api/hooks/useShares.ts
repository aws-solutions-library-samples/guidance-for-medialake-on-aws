import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useSnackbar } from "notistack";
import { publicApiClient } from "../publicApiClient";

export interface CreateShareOptions {
  expiresIn?: number; // Seconds until expiration (optional)
  representationType: "proxy" | "original";
  allowMetadata: boolean;
  allowEmbedding: boolean;
}

export interface CreateShareParams {
  assetId: string;
  options: CreateShareOptions;
}

export interface Share {
  ShareToken: string;
  AssetID: string;
  CreatedBy: string;
  CreatedAt: number;
  ExpiresAt?: number | null;
  Status: "active" | "revoked" | "expired";
  ShareType: string;
  AccessCount: number;
  DownloadCount: number;
  LastAccessedAt?: number | null;
  ShareSettings: {
    representationType: "proxy" | "original";
    allowMetadata: boolean;
    allowEmbedding: boolean;
  };
  Metadata?: {
    ipAddress?: string;
    userAgent?: string;
  };
  // Constructed URL for the share link (not from backend)
  ShareURL?: string;
  // Indicates if the current user can edit/revoke this share (only from GET shares)
  IsOwner?: boolean;
}

export interface CreateShareResponse {
  shareItem: Share;
  shareToken: string;
  shareUrl: string;
  representationType: "proxy" | "original";
  expiresAt?: number | null;
  createdAt: number;
}

export interface PublicShareAsset {
  InventoryID: string;
  DigitalSourceAsset: {
    Type: string;
    CreateDate?: string;
    MainRepresentation: {
      Format?: string;
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: string;
            FullPath?: string;
          };
          FileInfo?: {
            Size: number;
          };
        };
      };
    };
  };
  viewUrl?: string | null;
  downloadUrl?: string | null;
  representationType: "proxy" | "original";
  Metadata?: Record<string, any>;
}

export interface PublicShareData {
  asset: PublicShareAsset;
  shareInfo: {
    allowEmbedding: boolean;
    representationType: "proxy" | "original";
    expiresAt?: number;
  };
}

export interface GenerateDownloadUrlResponse {
  downloadUrl: string;
}

/**
 * Hook to create a shareable URL for an asset
 */
export const useCreateShare = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: async ({ assetId, options }: CreateShareParams) => {
      logger.info("Creating share", { assetId, options });
      const response = await apiClient.post<{ data: CreateShareResponse }>(
        API_ENDPOINTS.SHARES.CREATE(assetId),
        options
      );
      return response.data.data;
    },
    onSuccess: (data, variables) => {
      logger.info("Share created successfully", data);
      // Invalidate shares list for this asset
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SHARES.FOR_ASSET(variables.assetId),
      });
      enqueueSnackbar("Share created successfully", { variant: "success" });
    },
    onError: (error: AxiosError<{ message: string }> | Error) => {
      logger.error("Failed to create share", error);
      const message =
        error instanceof AxiosError
          ? error.response?.data?.message || "Failed to create share"
          : "Failed to create share";
      enqueueSnackbar(message, { variant: "error" });
    },
  });
};

/**
 * Hook to get all shares for an asset
 */
export const useAssetShares = (assetId: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: QUERY_KEYS.SHARES.FOR_ASSET(assetId),
    queryFn: async () => {
      logger.info("Fetching shares for asset", { assetId });
      const response = await apiClient.get<{ data: { shares: Share[] } }>(
        API_ENDPOINTS.SHARES.GET_FOR_ASSET(assetId)
      );
      // Add constructed ShareURL to each share
      const shares = response.data.data.shares.map((share) => ({
        ...share,
        ShareURL: `${window.location.origin}/share/${share.ShareToken}`,
      }));
      return shares;
    },
    enabled: options?.enabled ?? true,
  });
};

/**
 * Hook to revoke a share
 */
export const useRevokeShare = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: async ({ assetId, shareToken }: { assetId: string; shareToken: string }) => {
      logger.info("Revoking share", { assetId, shareToken });
      const response = await apiClient.delete<{ data: { message: string } }>(
        API_ENDPOINTS.SHARES.REVOKE(assetId, shareToken)
      );
      return response.data.data;
    },
    onSuccess: (data, variables) => {
      logger.info("Share revoked successfully", data);
      // Invalidate shares list for this asset
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SHARES.FOR_ASSET(variables.assetId),
      });
      enqueueSnackbar("Share revoked successfully", { variant: "success" });
    },
    onError: (error: AxiosError<{ message: string }> | Error) => {
      logger.error("Failed to revoke share", error);
      const message =
        error instanceof AxiosError
          ? error.response?.data?.message || "Failed to revoke share"
          : "Failed to revoke share";
      enqueueSnackbar(message, { variant: "error" });
    },
  });
};

/**
 * Hook to access a public share (no authentication required)
 */
export const usePublicShare = (shareToken: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: QUERY_KEYS.SHARES.PUBLIC(shareToken),
    queryFn: async () => {
      logger.info("Fetching public share", { shareToken });
      const response = await publicApiClient.get<{ data: PublicShareData }>(
        API_ENDPOINTS.SHARES.PUBLIC_ACCESS(shareToken)
      );
      return response.data.data;
    },
    enabled: options?.enabled ?? true,
    retry: false, // Don't retry on 404 or expired shares
  });
};

/**
 * Hook to generate download URL for a public share
 */
export const useGenerateDownloadUrlMutation = () => {
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: async (shareToken: string) => {
      logger.info("Generating download URL", { shareToken });
      const response = await publicApiClient.post<{ data: GenerateDownloadUrlResponse }>(
        API_ENDPOINTS.SHARES.GENERATE_DOWNLOAD_URL(shareToken)
      );
      return response.data.data;
    },
    onSuccess: (data) => {
      logger.info("Download URL generated successfully", data);
      // Create and click an anchor element to trigger download
      const link = document.createElement("a");
      link.href = data.downloadUrl;
      link.setAttribute("download", "");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    onError: (error: AxiosError<{ message: string }> | Error) => {
      logger.error("Failed to generate download URL", error);
      const message =
        error instanceof AxiosError
          ? error.response?.data?.message || "Failed to generate download URL"
          : "Failed to generate download URL";
      enqueueSnackbar(message, { variant: "error" });
    },
  });
};
