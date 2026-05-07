/**
 * Hook to fetch user summaries via the collections API.
 *
 * This avoids requiring the separate `users:view` permission —
 * the `/collections/users` endpoint is gated by `collections:edit`
 * instead, so any user who can share collections can also see the
 * user list for the sharing autocomplete.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import type { User } from "@/api/types/api.types";

interface CollectionUsersResponse {
  success: boolean;
  data: {
    users: User[];
    count: number;
  };
  meta: {
    request_id: string;
  };
}

export const useCollectionUsers = (enabled = true) => {
  return useQuery<User[], Error>({
    queryKey: [...QUERY_KEYS.COLLECTIONS.lists(), "users"],
    enabled,
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<CollectionUsersResponse>(
          API_ENDPOINTS.COLLECTIONS.USERS,
          { signal, skipAccessDeniedRedirect: true } as any
        );
        return (response.data.data?.users || []).map((user) => ({
          ...user,
          permissions: user.permissions || [],
        }));
      } catch (error: any) {
        if (error?.response?.status === 403) {
          logger.warn("No permission for collections users, returning empty list");
          return [];
        }
        logger.error("Fetch collection users error:", error);
        throw error;
      }
    },
  });
};
