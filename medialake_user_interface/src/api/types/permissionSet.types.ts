// src/api/types/permissionSet.types.ts

export interface Permission {
  action: string;
  resource: string;
  effect: "Allow" | "Deny";
  conditions?: Record<string, any>;
}

export interface PermissionSet {
  id: string;
  name: string;
  description: string;
  permissions: Permission[] | Record<string, any>;
  isSystem: boolean;
  effectiveRole?: string;
  createdBy?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreatePermissionSetRequest {
  name: string;
  description: string;
  permissions: Permission[];
}

export interface UpdatePermissionSetRequest {
  name?: string;
  description?: string;
  permissions?: Permission[];
}

export interface PermissionSetListResponse {
  status: string;
  message: string;
  data: {
    permissionSets: PermissionSet[];
  };
}

export interface PermissionSetResponse {
  status: string;
  message: string;
  data: PermissionSet;
}
