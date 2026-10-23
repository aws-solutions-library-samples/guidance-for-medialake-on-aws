import { useCallback, useMemo } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";

// Matches the backend cap on POST /collections/membership.
const MAX_ASSET_IDS = 100;

interface MembershipResponse {
  data: { inCollection: string[] };
}

/**
 * Which of the given assets are in a collection the current user can access.
 * One batched request per page of assets; a failure just hides the badge.
 */
export const useAssetCollectionMembership = (assetIds: string[]) => {
  const ids = useMemo(() => [...new Set(assetIds)].slice(0, MAX_ASSET_IDS).sort(), [assetIds]);

  const { data } = useQuery<string[], Error>({
    queryKey: QUERY_KEYS.COLLECTIONS.membership(ids),
    queryFn: async ({ signal }) => {
      const response = await apiClient.post<MembershipResponse>(
        API_ENDPOINTS.COLLECTIONS.MEMBERSHIP,
        { assetIds: ids },
        { signal }
      );
      return response.data.data.inCollection;
    },
    enabled: ids.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const inCollection = useMemo(() => new Set(data ?? []), [data]);
  const isAssetInCollection = useCallback(
    (assetId: string) => inCollection.has(assetId),
    [inCollection]
  );

  return { isAssetInCollection };
};
