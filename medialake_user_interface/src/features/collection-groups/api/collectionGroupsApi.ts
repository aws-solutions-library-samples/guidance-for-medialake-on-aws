/**
 * API client for Collection Groups endpoints
 */

import { apiClient } from "@/api/apiClient";
import type {
  CollectionGroup,
  CreateGroupRequest,
  UpdateGroupRequest,
  AddCollectionsRequest,
  RemoveCollectionsRequest,
  CollectionGroupListResponse,
  CollectionGroupResponse,
} from "../types";

export const collectionGroupsApi = {
  /**
   * List all collection groups
   */
  list: async (params?: {
    search?: string;
    limit?: number;
    cursor?: string;
  }): Promise<CollectionGroupListResponse> => {
    const response = await apiClient.get<CollectionGroupListResponse>("/collections/groups", {
      params,
    });
    return response.data;
  },

  /**
   * Create a new collection group
   */
  create: async (data: CreateGroupRequest): Promise<CollectionGroupResponse> => {
    const response = await apiClient.post<CollectionGroupResponse>("/collections/groups", data);
    return response.data;
  },

  /**
   * Get a single collection group by ID
   */
  get: async (groupId: string): Promise<CollectionGroupResponse> => {
    const response = await apiClient.get<CollectionGroupResponse>(`/collections/groups/${groupId}`);
    return response.data;
  },

  /**
   * Update a collection group
   */
  update: async (groupId: string, data: UpdateGroupRequest): Promise<CollectionGroupResponse> => {
    const response = await apiClient.put<CollectionGroupResponse>(
      `/collections/groups/${groupId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete a collection group
   */
  delete: async (groupId: string): Promise<void> => {
    await apiClient.delete(`/collections/groups/${groupId}`);
  },

  /**
   * Add collections to a group
   */
  addCollections: async (
    groupId: string,
    data: AddCollectionsRequest
  ): Promise<CollectionGroupResponse> => {
    const response = await apiClient.post<CollectionGroupResponse>(
      `/collections/groups/${groupId}/collections`,
      data
    );
    return response.data;
  },

  /**
   * Remove collections from a group
   */
  removeCollections: async (
    groupId: string,
    data: RemoveCollectionsRequest
  ): Promise<CollectionGroupResponse> => {
    const response = await apiClient.delete<CollectionGroupResponse>(
      `/collections/groups/${groupId}/collections`,
      { data }
    );
    return response.data;
  },
};
