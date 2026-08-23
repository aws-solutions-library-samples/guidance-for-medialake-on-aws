/**
 * Generic per-user settings store.
 *
 * Backs onto the existing `/users/settings` API, which stores one DynamoDB row per
 * (user, namespace, key) as `PK=USER#{sub}`, `SK=SETTING#{namespace}#{key}` with an
 * arbitrary JSON `value`. The user id comes from the authorizer context server-side and is
 * never sent by the client.
 *
 * Two properties of the backend shape this hook:
 *
 * 1. `GET /users/settings` does NOT use ConsistentRead, so a read straight after a write
 *    can be stale. We therefore write through the cache optimistically and reconcile from
 *    the mutation response, and never invalidate on success — the same approach
 *    `useFavorites` takes.
 * 2. `PUT` is a whole-value overwrite (`put_item`). Callers that store a collection must
 *    read-modify-write, which means concurrent tabs can lose an edit. Acceptable for
 *    small, rarely-edited, single-user lists.
 *
 * There is no DELETE route: "removing" a setting means writing an empty value.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";

/** A namespace's settings: `{ [key]: value }`. */
export type UserSettingsNamespace = Record<string, unknown>;

interface UserSettingsResponse {
  data?: {
    userId?: string;
    settings?: Record<string, UserSettingsNamespace>;
  };
  // API Gateway sometimes hands back a JSON string body
  body?: string;
}

/**
 * Read one namespace of the current user's settings.
 *
 * Returns `{}` rather than throwing when the user has no settings yet, and also when the
 * request fails — these are optional preferences and must never block the surface that
 * reads them. A 403 is swallowed with `skipAccessDeniedRedirect` so a permission surprise
 * can't eject the user from the page they're on.
 */
export const useGetUserSettings = (namespace: string) =>
  useQuery<UserSettingsNamespace, Error>({
    queryKey: QUERY_KEYS.USER_SETTINGS.namespace(namespace),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<UserSettingsResponse>(
          `${API_ENDPOINTS.USER_SETTINGS.BASE}?namespace=${encodeURIComponent(namespace)}`,
          { signal, skipAccessDeniedRedirect: true } as never
        );

        const payload =
          typeof response.data?.body === "string"
            ? (JSON.parse(response.data.body) as UserSettingsResponse)
            : response.data;

        return payload?.data?.settings?.[namespace] ?? {};
      } catch (error) {
        // A cancelled request must reject. React Query would otherwise cache this `{}` as
        // real data — and since `usePutUserSetting.onMutate` calls `cancelQueries`, that
        // would replace the optimistic value it just wrote with an empty namespace.
        if (signal?.aborted) throw error;
        logger.warn(`Failed to load user settings for namespace "${namespace}"`, error);
        return {};
      }
    },
    staleTime: 60 * 1000,
    gcTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: false,
  });

interface PutSettingVariables {
  namespace: string;
  key: string;
  value: unknown;
}

interface PutSettingContext {
  previous: UserSettingsNamespace | undefined;
}

/**
 * Write one setting key. Optimistically updates the cached namespace so callers see their
 * change immediately despite the eventually-consistent read, and rolls back on failure.
 */
export const usePutUserSetting = () => {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, PutSettingVariables, PutSettingContext>({
    mutationFn: async ({ namespace, key, value }) => {
      const response = await apiClient.put(API_ENDPOINTS.USER_SETTINGS.SETTING(namespace, key), {
        value,
      });
      return response.data;
    },
    onMutate: async ({ namespace, key, value }) => {
      const queryKey = QUERY_KEYS.USER_SETTINGS.namespace(namespace);
      await queryClient.cancelQueries({ queryKey });

      const previous = queryClient.getQueryData<UserSettingsNamespace>(queryKey);
      queryClient.setQueryData<UserSettingsNamespace>(queryKey, {
        ...(previous ?? {}),
        [key]: value,
      });

      return { previous };
    },
    onError: (error, { namespace }, context) => {
      if (context) {
        queryClient.setQueryData(QUERY_KEYS.USER_SETTINGS.namespace(namespace), context.previous);
      }
      logger.error("Failed to save user setting", error);
    },
    // Deliberately no invalidation on success: the GET is not consistent, so refetching
    // here could read back the pre-write value and undo what the user just did.
  });
};
