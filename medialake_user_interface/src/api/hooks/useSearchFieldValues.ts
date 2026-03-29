import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { useSearchFields } from "./useSearchFields";

interface FieldValuesResponse {
  status: string;
  data: Record<string, string[]> | null;
}

/**
 * Eagerly fetches distinct values for all filterable string fields with
 * autoPopulateValues enabled. Fires as soon as the field config is loaded
 * (i.e. right after login) so values are cached before the user opens the
 * filter modal.
 */
export const useSearchFieldValues = () => {
  const { data: fieldsData } = useSearchFields();

  const fieldNames =
    fieldsData?.data?.availableFields
      ?.filter((f) => f.isFilterable && f.autoPopulateValues && f.type === "string" && !f.isDefault)
      .map((f) => f.name) ?? [];

  return useQuery<Record<string, string[]>>({
    queryKey: QUERY_KEYS.SEARCH.fieldValues(fieldNames),
    queryFn: async () => {
      if (fieldNames.length === 0) return {};
      const response = await apiClient.post<FieldValuesResponse>(
        API_ENDPOINTS.SEARCH_FIELDS_VALUES,
        { fields: fieldNames }
      );
      return response.data?.data ?? {};
    },
    enabled: fieldNames.length > 0,
    staleTime: 1000 * 60 * 5, // 5 minutes — values don't change often
    gcTime: 1000 * 60 * 30,
  });
};
