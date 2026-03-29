import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { QUERY_KEYS } from "@/api/queryKeys";
import axios from "axios";

export interface MetadataFieldConfig {
  name: string;
  displayName: string;
  type: string;
  isDisplayable: boolean;
  isFilterable: boolean;
  autoPopulateValues?: boolean;
  predefinedValues?: string[];
}

export interface MetadataFieldsConfigResponse {
  status: string;
  message: string;
  data: { fields: MetadataFieldConfig[]; updatedAt?: string };
}

export const useMetadataFieldsConfig = () => {
  return useQuery<MetadataFieldsConfigResponse>({
    queryKey: QUERY_KEYS.SYSTEM_SETTINGS.metadataFields(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<MetadataFieldsConfigResponse>(
          API_ENDPOINTS.SYSTEM_SETTINGS.METADATA_FIELDS,
          { signal }
        );

        return response.data;
      } catch (error) {
        // 404 means no config saved yet — return empty fields
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return {
            status: "200",
            message: "No configuration found",
            data: { fields: [] },
          };
        }
        logger.error("Metadata fields config fetch error:", error);
        throw error;
      }
    },
    staleTime: 1000 * 60 * 10, // Cache for 10 minutes — invalidated on save
    gcTime: 1000 * 60 * 30,
  });
};
