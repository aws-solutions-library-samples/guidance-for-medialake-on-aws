import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";

export interface JitProvisioningSettings {
  /** Whether new federated users are assigned the default group. */
  enabled: boolean;
  /** Group id assigned on a user's first sign-in through an external IdP. */
  defaultGroupId: string;
  /**
   * Whether the deployment supports the feature at all. When false the
   * permissions the Cognito trigger needs were not deployed, so the setting
   * cannot take effect until the deployment configuration is changed.
   */
  capabilityEnabled: boolean;
  updatedAt?: string | null;
  updatedBy?: string | null;
  /** True when no administrator has saved a policy yet. */
  isDefault?: boolean;
}

export interface JitProvisioningSettingsResponse {
  status: string;
  message?: string;
  data: JitProvisioningSettings;
}

const FALLBACK: JitProvisioningSettingsResponse = {
  status: "success",
  message: "No configuration found",
  data: {
    enabled: false,
    defaultGroupId: "",
    capabilityEnabled: false,
    updatedAt: null,
    updatedBy: null,
    isDefault: true,
  },
};

export const useJitProvisioningSettings = () => {
  return useQuery<JitProvisioningSettingsResponse>({
    queryKey: QUERY_KEYS.SYSTEM_SETTINGS.jitProvisioning(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<JitProvisioningSettingsResponse>(
          API_ENDPOINTS.SYSTEM_SETTINGS.JIT_PROVISIONING,
          { signal, skipAccessDeniedRedirect: true } as any
        );
        return response.data;
      } catch (error) {
        // Treat "nothing saved yet" (404) as an empty policy so the settings
        // page still renders. Access-denied (403) propagates to the error
        // state — caching it as a successful "capability disabled" response
        // would misrepresent a permissions problem as deployment state.
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return FALLBACK;
        }
        logger.error("JIT provisioning settings fetch error:", error);
        throw error;
      }
    },
    staleTime: 1000 * 60 * 5,
    gcTime: 1000 * 60 * 30,
  });
};
