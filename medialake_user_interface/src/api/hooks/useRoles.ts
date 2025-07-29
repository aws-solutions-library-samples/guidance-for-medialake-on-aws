import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  Role,
  CreateRoleRequest,
  UpdateRoleRequest,
  RoleListResponse,
  RoleResponse,
} from "../types/api.types";

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
      console.log("Fetching roles...");
      const { data } = await apiClient.get<any>(API_ENDPOINTS.ROLES);

      console.log("API Response:", JSON.stringify(data, null, 2));

      // Handle string body format
      if (typeof data.body === "string") {
        console.log("Response body is a string, attempting to parse...");
        const parsedBody = JSON.parse(data.body);
        console.log("Parsed body:", parsedBody);

        if (parsedBody.data && Array.isArray(parsedBody.data.roles)) {
          console.log("Found roles array in parsed body data");
          return parsedBody.data.roles;
        }
      }

      // Handle body.roles format
      if (data.body && Array.isArray(data.body.roles)) {
        console.log("Found roles array directly in body");
        return data.body.roles;
      }

      // Handle body.data.roles format
      if (data.body && data.body.data && Array.isArray(data.body.data.roles)) {
        console.log("Found roles array in nested data structure");
        return data.body.data.roles;
      }

      // Handle direct response format {status, message, data: {roles: []}}
      if (data.status && data.data && Array.isArray(data.data.roles)) {
        console.log("Found roles array in direct response data");
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

  return useMutation<
    RoleResponse,
    Error,
    { id: string; updates: UpdateRoleRequest }
  >({
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
