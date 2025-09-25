import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  AssignPermissionSetRequest,
  UserAssignmentListResponse,
  GroupAssignmentListResponse,
  AssignmentResponse,
} from "../types/assignment.types";

// User Assignment Hooks
export const useListUserAssignments = (userId: string) => {
  // Add a unique identifier to track each hook instance
  const hookId = React.useId
    ? React.useId()
    : Math.random().toString(36).substring(7);

  return useQuery<UserAssignmentListResponse["data"], Error>({
    queryKey: QUERY_KEYS.ASSIGNMENTS.user.list(userId),
    queryFn: async () => {
      try {
        console.log(
          `Fetching assignments for user: ${userId} from hook instance: ${hookId}`,
        );
        const { data } = await apiClient.get<any>(
          API_ENDPOINTS.ASSIGNMENTS.USER.BASE(userId),
        );
        console.log(
          `User assignments API response for hook instance: ${hookId}`,
          data,
        );

        // Handle string body format
        if (typeof data.body === "string") {
          const parsedBody = JSON.parse(
            data.body,
          ) as UserAssignmentListResponse;
          console.log("Parsed user assignments from string:", parsedBody.data);
          return parsedBody.data;
        }

        // Handle nested body.data format
        if (data.body && data.body.data) {
          console.log("User assignments from data.body:", data.body.data);
          return data.body.data;
        }

        // Handle direct response format {status, message, data: {...}}
        if (data.status && data.data) {
          console.log("User assignments from direct response:", data.data);
          return data.data;
        }

        console.error("Unexpected API response structure:", data);
        return { assignments: [] }; // Return empty assignments instead of throwing
      } catch (error: any) {
        // Handle 403 errors gracefully
        if (error?.response?.status === 403) {
          console.log(
            `User assignments API returned 403 Forbidden for hook instance: ${hookId}`,
          );
          console.log(
            "User likely does not have permission to access assignments",
          );
          // Return empty assignments instead of throwing an error
          return { assignments: [] };
        }
        // Re-throw other errors
        throw error;
      }
    },
    enabled: !!userId,
  });
};

export const useAssignPsToUser = () => {
  const queryClient = useQueryClient();

  return useMutation<
    AssignmentResponse,
    Error,
    { userId: string; request: AssignPermissionSetRequest }
  >({
    mutationFn: async ({ userId, request }) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.ASSIGNMENTS.USER.BASE(userId), request);
      return JSON.parse(data.body);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.ASSIGNMENTS.user.all(variables.userId),
      });
      // Also invalidate users query to refresh their permission sets
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};

export const useRemoveUserAssignment = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { userId: string; permissionSetId: string }>({
    mutationFn: async ({ userId, permissionSetId }) => {
      await apiClient.delete(
        API_ENDPOINTS.ASSIGNMENTS.USER.REMOVE(userId, permissionSetId),
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.ASSIGNMENTS.user.all(variables.userId),
      });
      // Also invalidate users query to refresh their permission sets
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};

// Group Assignment Hooks
export const useListGroupAssignments = (groupId: string) => {
  // Add a unique identifier to track each hook instance
  const hookId = React.useId
    ? React.useId()
    : Math.random().toString(36).substring(7);

  return useQuery<GroupAssignmentListResponse["data"], Error>({
    queryKey: QUERY_KEYS.ASSIGNMENTS.group.list(groupId),
    queryFn: async () => {
      try {
        console.log(
          `Fetching assignments for group: ${groupId} from hook instance: ${hookId}`,
        );
        const { data } = await apiClient.get<any>(
          API_ENDPOINTS.ASSIGNMENTS.GROUP.BASE(groupId),
        );
        console.log(
          `Group assignments API response for hook instance: ${hookId}`,
          data,
        );

        // Handle string body format
        if (typeof data.body === "string") {
          const parsedBody = JSON.parse(
            data.body,
          ) as GroupAssignmentListResponse;
          console.log("Parsed group assignments from string:", parsedBody.data);
          return parsedBody.data;
        }

        // Handle nested body.data format
        if (data.body && data.body.data) {
          console.log("Group assignments from data.body:", data.body.data);
          return data.body.data;
        }

        // Handle direct response format {status, message, data: {...}}
        if (data.status && data.data) {
          console.log("Group assignments from direct response:", data.data);
          return data.data;
        }

        console.error("Unexpected API response structure:", data);
        return { assignments: [] }; // Return empty assignments instead of throwing
      } catch (error: any) {
        // Handle 403 errors gracefully
        if (error?.response?.status === 403) {
          console.log(
            `Group assignments API returned 403 Forbidden for hook instance: ${hookId}`,
          );
          console.log(
            "User likely does not have permission to access group assignments",
          );
          // Return empty assignments instead of throwing an error
          return { assignments: [] };
        }
        // Re-throw other errors
        throw error;
      }
    },
    enabled: !!groupId,
  });
};

export const useAssignPsToGroup = () => {
  const queryClient = useQueryClient();

  return useMutation<
    AssignmentResponse,
    Error,
    { groupId: string; request: AssignPermissionSetRequest }
  >({
    mutationFn: async ({ groupId, request }) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.ASSIGNMENTS.GROUP.BASE(groupId), request);
      return JSON.parse(data.body);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.ASSIGNMENTS.group.all(variables.groupId),
      });
      // Also invalidate groups query to refresh their permission sets
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GROUPS.all });
      // Also invalidate users query as their effective permissions might have changed
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};

export const useRemoveGroupAssignment = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { groupId: string; permissionSetId: string }>(
    {
      mutationFn: async ({ groupId, permissionSetId }) => {
        await apiClient.delete(
          API_ENDPOINTS.ASSIGNMENTS.GROUP.REMOVE(groupId, permissionSetId),
        );
      },
      onSuccess: (_, variables) => {
        queryClient.invalidateQueries({
          queryKey: QUERY_KEYS.ASSIGNMENTS.group.all(variables.groupId),
        });
        // Also invalidate groups query to refresh their permission sets
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GROUPS.all });
        // Also invalidate users query as their effective permissions might have changed
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
      },
    },
  );
};
