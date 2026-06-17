import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { useSearchFields } from "./useSearchFields";
import type { FacetBucket } from "./useSearch";

interface FieldValuesResponse {
  status: string;
  data: Record<string, FacetBucket[]> | null;
}

/**
 * Eagerly fetches distinct values (with doc counts) for all filterable string
 * fields with autoPopulateValues enabled.  Fires as soon as the field config
 * is loaded so the filter modal can display values + counts immediately,
 * without waiting for a search to be performed.
 *
 * Returns `{ data, refetch }` — call `refetch()` when the filter modal opens
 * to get fresh counts while still showing the cached data instantly.
 */
export const useSearchFieldValues = () => {
  const { data: fieldsData } = useSearchFields();

  const fieldNames =
    fieldsData?.data?.availableFields
      ?.filter((f) => f.isFilterable && f.autoPopulateValues && f.type === "string" && !f.isDefault)
      .map((f) => f.name) ?? [];

  return useQuery<Record<string, FacetBucket[]>>({
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

/**
 * Returns a callback that background-refreshes the field-values cache.
 * The stale cached data remains available while the refresh is in flight.
 */
export const useRefreshFieldValues = () => {
  const queryClient = useQueryClient();
  return useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: [...QUERY_KEYS.SEARCH.all, "fieldValues"],
    });
  }, [queryClient]);
};
