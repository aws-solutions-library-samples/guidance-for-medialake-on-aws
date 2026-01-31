/**
 * TypeScript interfaces for Collection Groups feature
 */

export interface CollectionGroup {
  id: string;
  name: string;
  description?: string;
  ownerId: string;
  isPublic: boolean;
  collectionIds: string[];
  collectionCount: number;
  createdAt: string;
  updatedAt: string;
  isOwner?: boolean;
  userRole?: string;
}

export interface CreateGroupRequest {
  name: string;
  description?: string;
  isPublic?: boolean;
}

export interface UpdateGroupRequest {
  name?: string;
  description?: string;
  isPublic?: boolean;
}

export interface AddCollectionsRequest {
  collectionIds: string[];
}

export interface RemoveCollectionsRequest {
  collectionIds: string[];
}

export interface CollectionGroupListResponse {
  success: boolean;
  data: CollectionGroup[];
  pagination?: {
    has_next_page: boolean;
    has_prev_page: boolean;
    limit: number;
    next_cursor?: string;
  };
  meta: {
    timestamp: string;
    version: string;
    request_id?: string;
  };
}

export interface CollectionGroupResponse {
  success: boolean;
  data: CollectionGroup;
  meta: {
    timestamp: string;
    version: string;
    request_id?: string;
  };
}
