import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import { Role, CreateRoleRequest, UpdateRoleRequest, RoleResponse } from "../types/api.types";

// export const useGetRoles = () => {
//     return useQuery<Role[], Error>({
//         queryKey: QUERY_KEYS.ROLES.all,
//         queryFn: async () => {
//             const { data } = await apiClient.get<{ statusCode: number; body: string }>(API_ENDPOINTS.ROLES);
//             const parsedBody = JSON.parse(data.body) as RoleListResponse;
//             return parsedBody.data.roles;
//         }
//     });
// };

export const useGetRoles = () => {
  return useQuery<Role[], Error>({
    queryKey: QUERY_KEYS.ROLES.all,
    queryFn: async () => {
      const { data } = await apiClient.get<any>(API_ENDPOINTS.ROLES);

      // Handle string body format
      if (typeof data.body === "string") {
        const parsedBody = JSON.parse(data.body);

        if (parsedBody.data && Array.isArray(parsedBody.data.roles)) {
          return parsedBody.data.roles;
        }
      }

      // Handle body.roles format
      if (data.body && Array.isArray(data.body.roles)) {
        return data.body.roles;
      }

      // Handle body.data.roles format
      if (data.body && data.body.data && Array.isArray(data.body.data.roles)) {
        return data.body.data.roles;
      }

      // Handle direct response format {status, message, data: {roles: []}}
      if (data.status && data.data && Array.isArray(data.data.roles)) {
        return data.data.roles;
      }

      console.error("Unexpected API response structure:", data);
      return [];
    },
  });
};
export const useCreateRole = () => {
  const queryClient = useQueryClient();

  return useMutation<RoleResponse, Error, CreateRoleRequest>({
    mutationFn: async (roleData) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.ROLES, roleData);
      return JSON.parse(data.body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLES.all });
    },
  });
};

export const useUpdateRole = () => {
  const queryClient = useQueryClient();

  return useMutation<RoleResponse, Error, { id: string; updates: UpdateRoleRequest }>({
    mutationFn: async ({ id, updates }) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(`${API_ENDPOINTS.ROLES}/${id}`, updates);
      return JSON.parse(data.body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLES.all });
    },
  });
};

export const useDeleteRole = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (roleId) => {
      await apiClient.delete(`${API_ENDPOINTS.ROLES}/${roleId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLES.all });
    },
  });
};
