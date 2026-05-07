import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";

export interface GroupPermissionsData {
  groupId: string;
  permissionSetId?: string;
  permissions: Array<{
    action: string;
    resource: string;
    effect: string;
  }>;
  updatedAt?: string;
}

export interface UpdateGroupPermissionsRequest {
  groupId: string;
  permissions: Array<{
    action: string;
    resource: string;
    effect: string;
  }>;
}

/**
 * Fetch the permissions for a specific group.
 * This calls GET /groups/{groupId}/permissions which returns the
 * permission set associated with the group.
 */
export const useGetGroupPermissions = (groupId: string) => {
  return useQuery<GroupPermissionsData, Error>({
    queryKey: QUERY_KEYS.GROUP_PERMISSIONS.detail(groupId),
    enabled: !!groupId,
    queryFn: async () => {
      const { data } = await apiClient.get<any>(API_ENDPOINTS.GROUP_PERMISSIONS.GET(groupId));

      // Handle string body format
      if (typeof data.body === "string") {
        const parsedBody = JSON.parse(data.body);
        return parsedBody.data || parsedBody;
      }

      // Handle body.data format
      if (data.body && data.body.data) {
        return data.body.data;
      }

      // Handle direct response format
      if (data.data) {
        return data.data;
      }

      return { groupId, permissions: [] };
    },
  });
};

/**
 * Update the permissions for a group.
 * This calls PUT /groups/{groupId}/permissions which auto-syncs
 * the associated permission set on the backend.
 */
export const useUpdateGroupPermissions = () => {
  const queryClient = useQueryClient();

  return useMutation<any, Error, UpdateGroupPermissionsRequest>({
    mutationFn: async ({ groupId, permissions }) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.GROUP_PERMISSIONS.UPDATE(groupId), { permissions });

      if (typeof data.body === "string") {
        return JSON.parse(data.body);
      }
      return data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUP_PERMISSIONS.detail(variables.groupId),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUPS.detail(variables.groupId),
      });
    },
  });
};
