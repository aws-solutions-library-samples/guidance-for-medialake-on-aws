/**
 * React Query hooks for Collection Groups
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { collectionGroupsApi } from "../api/collectionGroupsApi";
import type {
  CreateGroupRequest,
  UpdateGroupRequest,
  AddCollectionsRequest,
  RemoveCollectionsRequest,
} from "../types";

/**
 * Hook to fetch list of collection groups
 */
export const useCollectionGroups = (params?: {
  search?: string;
  limit?: number;
  cursor?: string;
}) => {
  return useQuery({
    queryKey: ["collection-groups", params],
    queryFn: () => collectionGroupsApi.list(params),
  });
};

/**
 * Hook to fetch a single collection group
 */
export const useCollectionGroup = (groupId: string) => {
  return useQuery({
    queryKey: ["collection-group", groupId],
    queryFn: () => collectionGroupsApi.get(groupId),
    enabled: !!groupId,
  });
};

/**
 * Hook to create a new collection group
 */
export const useCreateCollectionGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateGroupRequest) => collectionGroupsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection-groups"] });
    },
  });
};

/**
 * Hook to update a collection group
 */
export const useUpdateCollectionGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, data }: { groupId: string; data: UpdateGroupRequest }) =>
      collectionGroupsApi.update(groupId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collection-groups"] });
      queryClient.invalidateQueries({
        queryKey: ["collection-group", variables.groupId],
      });
    },
  });
};

/**
 * Hook to delete a collection group
 */
export const useDeleteCollectionGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (groupId: string) => collectionGroupsApi.delete(groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection-groups"] });
    },
  });
};

/**
 * Hook to add collections to a group
 */
export const useAddCollectionsToGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, data }: { groupId: string; data: AddCollectionsRequest }) =>
      collectionGroupsApi.addCollections(groupId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collection-groups"] });
      queryClient.invalidateQueries({
        queryKey: ["collection-group", variables.groupId],
      });
      // Also invalidate collections list as group membership changed
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
};

/**
 * Hook to remove collections from a group
 */
export const useRemoveCollectionsFromGroup = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ groupId, data }: { groupId: string; data: RemoveCollectionsRequest }) =>
      collectionGroupsApi.removeCollections(groupId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["collection-groups"] });
      queryClient.invalidateQueries({
        queryKey: ["collection-group", variables.groupId],
      });
      // Also invalidate collections list as group membership changed
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
};
