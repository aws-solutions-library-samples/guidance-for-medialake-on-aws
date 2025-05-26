// src/permissions/components/PermissionGuard.tsx
import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';
import { Actions, Subjects } from '../types/ability.types';
import { PermissionGuardProps } from '../types/permission.types';
import { permissionCache } from '../utils/permission-cache';

/**
 * Higher-order component for protecting routes based on permissions
 * 
 * @param props Component props
 * @returns React element or redirect
 */
export function PermissionGuard({ 
  action, 
  subject, 
  field, 
  fallback = null, 
  children 
}: PermissionGuardProps) {
  const { can, loading } = usePermission();
  const location = useLocation();
  
  // Clear the permission cache when the component mounts
  // This ensures that we always get a fresh permission check
  useEffect(() => {
    console.log('PermissionGuard: Clearing permission cache');
    permissionCache.clear();
  }, []);
  
  // Show loading state if permissions are still loading
  if (loading) {
    return <div>Loading permissions...</div>;
  }
  
  // Check if the user has permission
  console.log(`PermissionGuard: Checking permission for ${action} on ${subject}`);
  const allowed = can(action, subject, field);
  console.log(`PermissionGuard: Permission check result: ${allowed}`);
  
  // If allowed, render the children
  if (allowed) {
    return <>{children}</>;
  }
  
  // If fallback is provided, render it
  if (fallback) {
    return <>{fallback}</>;
  }
  
  // Otherwise, redirect to the login page or access denied page
  return <Navigate to="/access-denied" state={{ from: location }} replace />;
}

/**
 * Higher-order component for creating a route guard
 * 
 * @param action The action to check
 * @param subject The subject to check
 * @param field Optional field to check
 * @returns A function that takes a component and returns a guarded component
 */
export function withPermission(action: Actions, subject: Subjects, field?: string) {
  return function(Component: React.ComponentType<any>) {
    return function WithPermissionComponent(props: any) {
      return (
        <PermissionGuard action={action} subject={subject} field={field}>
          <Component {...props} />
        </PermissionGuard>
      );
    };
  };
}

/**
 * Component for protecting routes in a router configuration
 * 
 * @param props Component props
 * @returns React element or null
 */
export function RoutePermissionGuard({ 
  permission, 
  element 
}: { 
  permission: { action: Actions; subject: Subjects; field?: string }; 
  element: React.ReactNode;
}) {
  return (
    <PermissionGuard 
      action={permission.action} 
      subject={permission.subject} 
      field={permission.field}
    >
      {element}
    </PermissionGuard>
  );
}