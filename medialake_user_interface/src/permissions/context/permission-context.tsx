// src/permissions/context/permission-context.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Ability } from '@casl/ability';
import { AppAbility, Actions, Subjects, createAppAbility } from '../types/ability.types';
import { PermissionContextType, User } from '../types/permission.types';
import { defineAbilityFor, extractUserFromClaims } from '../utils/ability-factory';
import { transformPermissions } from '../transformers/permission-transformer';
import { useGetPermissionSets } from '../../api/hooks/usePermissionSets';
import { useAuth } from '../../common/hooks/auth-context';
import { StorageHelper } from '../../common/helpers/storage-helper';
import { permissionCache } from '../utils/permission-cache';

// Create the permission context with default values
const PermissionContext = createContext<PermissionContextType>({
  ability: createAppAbility(),
  loading: true,
  error: null,
  refreshPermissions: async () => {},
});

/**
 * Permission Provider component that makes the ability instance available
 * throughout the app
 */
export function PermissionProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [ability, setAbility] = useState<AppAbility>(() => createAppAbility());
  
  // Get permission sets from API
  const { 
    data: permissionSets, 
    isLoading, 
    error, 
    refetch 
  } = useGetPermissionSets();

  // Extract user information from JWT token
  useEffect(() => {
    if (isAuthenticated) {
      try {
        const token = StorageHelper.getToken();
        if (token) {
          // Parse the JWT token to get user claims
          const tokenParts = token.split('.');
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            const extractedUser = extractUserFromClaims(payload);
            setUser(extractedUser);
          }
        }
      } catch (error) {
        console.error('Error extracting user from token:', error);
      }
    } else {
      setUser(null);
    }
  }, [isAuthenticated]);

  // Update ability when user or permission sets change
  useEffect(() => {
    console.log('Permission context effect triggered');
    console.log('isAuthenticated:', isAuthenticated);
    console.log('user:', user);
    console.log('permissionSets:', permissionSets);
    
    if (isAuthenticated && user) {
      try {
        // Transform permission sets to the format expected by CASL
        const transformedPermissions = transformPermissions(permissionSets || []);
        console.log('Transformed permissions:', transformedPermissions);
        
        // Clear the permission cache before creating a new ability
        console.log('Clearing permission cache before creating new ability');
        permissionCache.clear();
        
        // Create the ability instance
        const newAbility = defineAbilityFor(user, transformedPermissions);
        console.log('New ability created:', newAbility);
        setAbility(newAbility);
      } catch (error) {
        console.error('Error creating ability:', error);
      }
    } else {
      // Reset ability when not authenticated
      console.log('Resetting ability - not authenticated or no user');
      setAbility(createAppAbility());
    }
  }, [isAuthenticated, user, permissionSets]);

  // Function to refresh permissions
  const refreshPermissions = useCallback(async () => {
    if (isAuthenticated) {
      await refetch();
    }
  }, [isAuthenticated, refetch]);

  // Context value
  const value = {
    ability,
    loading: isLoading,
    error,
    refreshPermissions,
  };

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}

/**
 * Hook to use the permission context
 * @returns The permission context
 */
export function usePermissionContext() {
  const context = useContext(PermissionContext);
  if (context === undefined) {
    throw new Error('usePermissionContext must be used within a PermissionProvider');
  }
  return context;
}