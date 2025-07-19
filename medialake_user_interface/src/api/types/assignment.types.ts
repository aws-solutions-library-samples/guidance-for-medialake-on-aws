// src/api/types/assignment.types.ts

export interface Assignment {
  principalId: string; // User ID or Group ID
  principalType: "USER" | "GROUP";
  permissionSetId: string;
  assignedAt: string;
  assignedBy?: string;
}

export interface AssignPermissionSetRequest {
  permissionSetIds: string[];
}

export interface UserAssignmentListResponse {
  status: string;
  message: string;
  data: {
    userId: string;
    assignments: {
      permissionSetId: string;
      permissionSetName: string;
      assignedAt: string;
    }[];
  };
}

export interface GroupAssignmentListResponse {
  status: string;
  message: string;
  data: {
    groupId: string;
    assignments: {
      permissionSetId: string;
      permissionSetName: string;
      assignedAt: string;
    }[];
  };
}

export interface AssignmentResponse {
  status: string;
  message: string;
  data: {
    principalId: string;
    principalType: "USER" | "GROUP";
    assignments: {
      permissionSetId: string;
      permissionSetName: string;
      assignedAt: string;
    }[];
  };
}
