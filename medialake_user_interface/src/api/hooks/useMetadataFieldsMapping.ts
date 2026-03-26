import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { logger } from "@/common/helpers/logger";
import { QUERY_KEYS } from "@/api/queryKeys";

export interface MappingField {
  name: string;
  type: string;
  displayType: "string" | "number" | "date";
  keywordName: string | null;
}

export interface MetadataFieldsMappingResponse {
  status: string;
  message: string;
  data: { fields: MappingField[] };
}

export const useMetadataFieldsMapping = () => {
  return useQuery<MetadataFieldsMappingResponse>({
    queryKey: QUERY_KEYS.SEARCH.mapping(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<MetadataFieldsMappingResponse>(
          API_ENDPOINTS.SEARCH_FIELDS_MAPPING,
          { signal }
        );

        if (!response.data?.data?.fields) {
          throw new Error("Invalid metadata fields mapping response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Metadata fields mapping fetch error:", error);
        throw error;
      }
    },
    staleTime: 0,
  });
};
