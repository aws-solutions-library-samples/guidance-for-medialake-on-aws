import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  PermissionSet,
  CreatePermissionSetRequest,
  UpdatePermissionSetRequest,
  PermissionSetListResponse,
  PermissionSetResponse,
} from "../types/permissionSet.types";

export const useGetPermissionSets = (enabled = false) => {
  // Add a unique identifier to track each hook instance
  const hookId = React.useId();
  console.log(`useGetPermissionSets hook instance created: ${hookId}`);

  return useQuery<PermissionSet[], Error>({
    queryKey: QUERY_KEYS.PERMISSION_SETS.all,
    enabled: enabled,
    queryFn: async () => {
      try {
        console.log(
          `Fetching permission sets... [${new Date().toISOString()}] from hook instance: ${hookId}`,
        );
        const { data } = await apiClient.get<any>(
          API_ENDPOINTS.PERMISSION_SETS.BASE,
        );
        console.log(
          `Permission sets API response [${new Date().toISOString()}] for hook instance: ${hookId}`,
        );

        // Handle string body format (older API format)
        if (typeof data.body === "string") {
          const parsedBody = JSON.parse(data.body) as PermissionSetListResponse;
          console.log(
            "Parsed permission sets from string:",
            parsedBody.data.permissionSets,
          );
          return parsedBody.data.permissionSets;
        }

        // Handle nested body.data.permissionSets format
        if (
          data.body &&
          data.body.data &&
          Array.isArray(data.body.data.permissionSets)
        ) {
          console.log(
            "Permission sets from data.body:",
            data.body.data.permissionSets,
          );
          return data.body.data.permissionSets;
        }

        // Handle direct response format {status, message, data: {permissionSets: []}}
        if (
          data.status &&
          data.data &&
          Array.isArray(data.data.permissionSets)
        ) {
          console.log(
            "Permission sets from direct response:",
            data.data.permissionSets,
          );
          return data.data.permissionSets;
        }

        console.error("Unexpected API response structure:", data);
        return [];
      } catch (error: any) {
        // Handle 403 errors gracefully
        if (error?.response?.status === 403) {
          console.log(
            `Permission sets API returned 403 Forbidden for hook instance: ${hookId}`,
          );
          console.log(
            "User likely does not have permission to access permission sets",
          );
          // Return empty array instead of throwing an error
          return [];
        }
        // Re-throw other errors
        throw error;
      }
    },
  });
};

export const useGetPermissionSet = (id: string, enabled = true) => {
  return useQuery<PermissionSet, Error>({
    queryKey: QUERY_KEYS.PERMISSION_SETS.detail(id),
    enabled: enabled && !!id,
    queryFn: async () => {
      console.log(`Fetching permission set with id: ${id}`);
      const { data } = await apiClient.get<any>(
        API_ENDPOINTS.PERMISSION_SETS.GET(id),
      );
      console.log("Permission set API response:", data);

      // Handle string body format
      if (typeof data.body === "string") {
        const parsedBody = JSON.parse(data.body) as PermissionSetResponse;
        console.log("Parsed permission set from string:", parsedBody.data);
        return parsedBody.data;
      }

      // Handle nested body.data format
      if (data.body && data.body.data) {
        console.log("Permission set from data.body:", data.body.data);
        return data.body.data;
      }

      // Handle direct response format {status, message, data: {...}}
      if (data.status && data.data) {
        console.log("Permission set from direct response:", data.data);
        return data.data;
      }

      throw new Error("Failed to fetch permission set");
    },
  });
};

export const useCreatePermissionSet = () => {
  const queryClient = useQueryClient();

  return useMutation<PermissionSetResponse, Error, CreatePermissionSetRequest>({
    mutationFn: async (permissionSetData) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.PERMISSION_SETS.BASE, permissionSetData);
      return JSON.parse(data.body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.PERMISSION_SETS.all,
      });
    },
  });
};

export const useUpdatePermissionSet = () => {
  const queryClient = useQueryClient();

  return useMutation<
    PermissionSetResponse,
    Error,
    { id: string; updates: UpdatePermissionSetRequest }
  >({
    mutationFn: async ({ id, updates }) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.PERMISSION_SETS.UPDATE(id), updates);
      return JSON.parse(data.body);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.PERMISSION_SETS.all,
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.PERMISSION_SETS.detail(variables.id),
      });
    },
  });
};

export const useDeletePermissionSet = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (permissionSetId) => {
      await apiClient.delete(
        API_ENDPOINTS.PERMISSION_SETS.DELETE(permissionSetId),
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.PERMISSION_SETS.all,
      });
    },
  });
};
