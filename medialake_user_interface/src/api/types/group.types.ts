// src/api/types/group.types.ts

export interface Group {
  id: string;
  name: string;
  description: string;
  department?: string;
  assignedPermissionSets?: string[];
  members?: string[]; // Array of user IDs
  createdBy?: string;
  createdAt: string;
  updatedAt: string;
  entity?: string;
}

export interface CreateGroupRequest {
  name: string;
  id: string;
  description: string;
  department?: string;
  assignedPermissionSets?: string[];
}

export interface UpdateGroupRequest {
  name?: string;
  description?: string;
  department?: string;
  assignedPermissionSets?: string[];
}

export interface GroupListResponse {
  status: string;
  message: string;
  data: {
    groups: Group[];
  };
}

export interface GroupResponse {
  status: string;
  message: string;
  data: Group;
}

export interface AddGroupMembersRequest {
  userIds: string[];
}

export interface GroupMembersResponse {
  status: string;
  message: string;
  data: {
    groupId: string;
    members: string[];
  };
}
