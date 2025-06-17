// src/permissions/components/Can.tsx
import React from 'react';
import { usePermission } from '../hooks/usePermission';
import { CanProps } from '../types/permission.types';
import { Actions, Subjects } from '../types/ability.types';

/**
 * Component for conditional rendering based on permissions
 * 
 * @param props Component props
 * @returns React element or null
 */
export function Can({
  I: action,
  a: subject,
  field,
  passThrough = false,
  children
}: CanProps) {
  const { can, loading } = usePermission();
  
  console.log('Can component rendering with:', { action, subject, field });
  console.log('Can component loading state:', loading);
  
  // While permissions are loading, keep the current state (don't hide)
  // This prevents flickering when permissions are refreshed
  if (loading) {
    console.log('Can component: Permissions loading, keeping content visible');
    // During loading, we keep the content visible to prevent flickering
    // If children is a function, call it with true during loading
    if (typeof children === 'function') {
      return <>{children(true)}</>;
    }
    return <>{children}</>;
  }
  
  const allowed = can(action as Actions, subject as Subjects, field);
  
  console.log('Can component permission check result:', allowed);
  
  // If children is a function, call it with the allowed status
  if (typeof children === 'function') {
    console.log('Can component rendering function children with allowed:', allowed);
    return <>{children(allowed)}</>;
  }
  
  // If allowed, render the children
  if (allowed) {
    console.log('Can component rendering children (allowed)');
    return <>{children}</>;
  }
  
  // If passThrough is true, render the children with disabled styling
  if (passThrough) {
    console.log('Can component rendering children with disabled styling (passThrough)');
    return (
      <div
        style={{
          opacity: 0.5,
          pointerEvents: 'none',
          cursor: 'not-allowed'
        }}
      >
        {children}
      </div>
    );
  }
  
  // Otherwise, render nothing
  console.log('Can component rendering nothing (not allowed)');
  return null;
}

// PermissionGuard component moved to its own file