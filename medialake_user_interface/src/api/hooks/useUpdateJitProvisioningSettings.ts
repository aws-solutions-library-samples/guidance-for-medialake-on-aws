import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";
import type { JitProvisioningSettingsResponse } from "./useJitProvisioningSettings";

export interface UpdateJitProvisioningPayload {
  enabled: boolean;
  defaultGroupId: string;
  /** Value last read, used for optimistic concurrency. */
  expectedUpdatedAt?: string | null;
}

export const useUpdateJitProvisioningSettings = () => {
  const queryClient = useQueryClient();
  const { showError } = useErrorModal();

  return useMutation<JitProvisioningSettingsResponse, Error, UpdateJitProvisioningPayload>({
    mutationFn: async (payload) => {
      try {
        const response = await apiClient.put<JitProvisioningSettingsResponse>(
          API_ENDPOINTS.SYSTEM_SETTINGS.JIT_PROVISIONING,
          payload
        );
        return response.data;
      } catch (error) {
        logger.error("JIT provisioning settings update error:", error);
        if (axios.isAxiosError(error)) {
          if (error.response?.status === 409) {
            showError(
              "Conflict: the just-in-time provisioning settings were modified by another user. Please refresh and try again."
            );
          } else if (error.response?.status === 400) {
            // The API explains exactly why the group was rejected (missing from
            // the user pool, or too privileged), so surface it verbatim.
            const detail =
              (error.response?.data as any)?.message || "The selected group could not be used.";
            showError(detail);
          } else {
            showError("Failed to update just-in-time provisioning settings");
          }
        } else {
          showError("Failed to update just-in-time provisioning settings");
        }
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SYSTEM_SETTINGS.jitProvisioning(),
      });
    },
  });
};
