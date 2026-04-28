import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";
import type { MetadataFieldConfig, MetadataFieldsConfigResponse } from "./useMetadataFieldsConfig";

export interface UpdateMetadataFieldsPayload {
  fields: MetadataFieldConfig[];
  expectedUpdatedAt?: string | null;
}

export const useUpdateMetadataFieldsConfig = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<MetadataFieldsConfigResponse, Error, UpdateMetadataFieldsPayload>({
    mutationFn: async (payload) => {
      try {
        const response = await apiClient.put<MetadataFieldsConfigResponse>(
          API_ENDPOINTS.SYSTEM_SETTINGS.METADATA_FIELDS,
          payload
        );
        return response.data;
      } catch (error) {
        logger.error("Metadata fields config update error:", error);
        if (axios.isAxiosError(error) && error.response?.status === 409) {
          showError(
            "Conflict: the metadata fields configuration was modified by another user. Please refresh and try again."
          );
        } else {
          showError("Failed to update metadata fields configuration");
        }
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SYSTEM_SETTINGS.metadataFields(),
      });
      // Also invalidate the search fields query so the dropdown picks up changes immediately
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SEARCH.fields(),
      });
      // Invalidate eager field values so newly auto-populated fields get fetched
      queryClient.invalidateQueries({
        queryKey: [...QUERY_KEYS.SEARCH.all, "fieldValues"],
      });
    },
  });
};
