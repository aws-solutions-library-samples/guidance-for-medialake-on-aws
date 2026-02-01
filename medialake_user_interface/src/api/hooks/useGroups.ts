import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  Group,
  CreateGroupRequest,
  UpdateGroupRequest,
  GroupListResponse,
  GroupResponse,
  AddGroupMembersRequest,
  GroupMembersResponse,
} from "../types/group.types";

export const useGetGroups = (enabled: boolean = true) => {
  return useQuery<Group[], Error>({
    queryKey: QUERY_KEYS.GROUPS.all,
    enabled: enabled,
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<any>(API_ENDPOINTS.GROUPS.BASE);

        if (typeof data.body === "string") {
          const parsedBody = JSON.parse(data.body) as GroupListResponse;
          return parsedBody.data.groups;
        }

        if (data.body && data.body.data && Array.isArray(data.body.data.groups)) {
          return data.body.data.groups;
        }

        if (data.status && data.data && Array.isArray(data.data.groups)) {
          return data.data.groups;
        }

        return [];
      } catch (error: any) {
        if (error?.response?.status === 403) {
          return [];
        }
        // Re-throw other errors
        throw error;
      }
    },
  });
};

export const useGetGroup = (id: string) => {
  return useQuery<Group, Error>({
    queryKey: QUERY_KEYS.GROUPS.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<{ statusCode: number; body: any }>(
        API_ENDPOINTS.GROUPS.GET(id)
      );

      if (typeof data.body === "string") {
        const parsedBody = JSON.parse(data.body) as GroupResponse;
        return parsedBody.data;
      }

      if (data.body && data.body.data) {
        return data.body.data;
      }

      throw new Error("Failed to fetch group");
    },
    enabled: !!id,
  });
};

export const useCreateGroup = () => {
  const queryClient = useQueryClient();

  return useMutation<GroupResponse, Error, CreateGroupRequest>({
    mutationFn: async (groupData) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.GROUPS.BASE, groupData);
      return JSON.parse(data.body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GROUPS.all });
    },
  });
};

export const useUpdateGroup = () => {
  const queryClient = useQueryClient();

  return useMutation<GroupResponse, Error, { id: string; updates: UpdateGroupRequest }>({
    mutationFn: async ({ id, updates }) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.GROUPS.UPDATE(id), updates);
      return JSON.parse(data.body);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GROUPS.all });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUPS.detail(variables.id),
      });
    },
  });
};

export const useDeleteGroup = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (groupId) => {
      await apiClient.delete(API_ENDPOINTS.GROUPS.DELETE(groupId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GROUPS.all });
    },
  });
};

export const useAddGroupMembers = () => {
  const queryClient = useQueryClient();

  return useMutation<
    GroupMembersResponse,
    Error,
    { groupId: string; request: AddGroupMembersRequest }
  >({
    mutationFn: async ({ groupId, request }) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.GROUPS.ADD_MEMBERS(groupId), request);
      return JSON.parse(data.body);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUPS.detail(variables.groupId),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUPS.members(variables.groupId),
      });
      // Also invalidate users query to refresh their group memberships
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};

export const useRemoveGroupMember = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { groupId: string; userId: string }>({
    mutationFn: async ({ groupId, userId }) => {
      await apiClient.delete(API_ENDPOINTS.GROUPS.REMOVE_MEMBER(groupId, userId));
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUPS.detail(variables.groupId),
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.GROUPS.members(variables.groupId),
      });
      // Also invalidate users query to refresh their group memberships
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS.all });
    },
  });
};
