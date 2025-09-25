// src/permissions/types/permission.types.ts
import { Actions, Subjects, Conditions } from "./ability.types";

// Define the Permission interface
export interface Permission {
  id: string;
  principalId: string;
  principalType: "USER" | "GROUP";
  action: Actions;
  resource: Subjects;
  effect: "Allow" | "Deny";
  conditions?: Conditions;
}

// Define the PermissionSet interface
export interface PermissionSet {
  id: string;
  name: string;
  description?: string;
  permissions: Permission[];
  createdAt: string;
  updatedAt: string;
}

// Define the User interface for permission context
export interface User {
  id: string;
  username: string;
  groups: string[];
  [key: string]: any;
}

// Define the PermissionContextType interface
export interface PermissionContextType {
  ability: any;
  loading: boolean;
  error: Error | null;
  refreshPermissions: () => Promise<void>;
}

// Define the CanProps interface for the Can component
export interface CanProps {
  I: Actions;
  a: Subjects;
  field?: string;
  subject?: any;
  passThrough?: boolean;
  children: React.ReactNode | ((allowed: boolean) => React.ReactNode);
}

// Define the PermissionGuardProps interface for the PermissionGuard component
export interface PermissionGuardProps {
  action: Actions;
  subject: Subjects;
  field?: string;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}
