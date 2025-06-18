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
import PermissionTokenCache from '../utils/permission-token-cache';

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
  const { isAuthenticated, isLoading: authLoading, isInitialized } = useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [ability, setAbility] = useState<AppAbility>(() => createAppAbility());
  
  // State to control when to fetch permission sets from API
  const [shouldFetchPermissions, setShouldFetchPermissions] = useState(false);
  
  // Get permission sets from API only when explicitly enabled
  const {
    data: permissionSets,
    isLoading,
    error,
    refetch
  } = useGetPermissionSets(shouldFetchPermissions);

  // Extract user information from JWT token
  useEffect(() => {
    console.log('PermissionProvider: Auth state changed', { isAuthenticated, isInitialized, authLoading });
    
    if (isAuthenticated && isInitialized) {
      try {
        const token = StorageHelper.getToken();
        if (token) {
          // Check cache first
          const cached = PermissionTokenCache.get(token);
          if (cached) {
            console.log('Using cached user and permissions');
            const cachedUser = { ...cached.user, customPermissions: cached.customPermissions };
            setUser(cachedUser);
            return;
          }
          
          // Parse the JWT token to get user claims
          const tokenParts = token.split('.');
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            console.log('=== JWT Token Claims ===');
            console.log('Full token payload:', JSON.stringify(payload, null, 2));
            console.log('cognito:groups claim:', payload['cognito:groups']);
            console.log('custom:permissions claim:', payload['custom:permissions']);
            console.log('cognito:username claim:', payload['cognito:username']);
            console.log('sub claim:', payload.sub);
            console.log('email claim:', payload.email);
            console.log('======================');
            
            const extractedUser = extractUserFromClaims(payload);
            let customPermissions: string[] = [];
            
            // Parse custom:permissions from JWT
            if (payload['custom:permissions']) {
              try {
                customPermissions = JSON.parse(payload['custom:permissions']);
                console.log('Parsed custom permissions:', customPermissions);
                // Store permissions in user object
                extractedUser.customPermissions = customPermissions;
              } catch (e) {
                console.error('Failed to parse custom:permissions:', e);
              }
            }
            
            // Cache the permissions with token expiry
            const exp = payload.exp;
            if (exp) {
              const expiresIn = exp - Math.floor(Date.now() / 1000); // Time until expiry in seconds
              if (expiresIn > 0) {
                PermissionTokenCache.set(extractedUser, customPermissions, token, expiresIn);
              }
            }
            
            console.log('Extracted user from claims:', extractedUser);
            setUser(extractedUser);
          }
        }
      } catch (error) {
        console.error('Error extracting user from token:', error);
      }
    } else {
      setUser(null);
      PermissionTokenCache.clear(); // Clear cache on logout
    }
  }, [isAuthenticated, isInitialized]);

  // Listen for storage changes (token updates) to refresh permissions
  useEffect(() => {
    if (!isAuthenticated) return;
    
    const handleStorageChange = (e: StorageEvent) => {
      // Handle token changes in storage
      if (e.key === 'medialake-auth-token' && e.newValue !== e.oldValue) {
        console.log('Token changed in storage, refreshing permissions...');
        
        const newToken = e.newValue;
        if (newToken) {
          try {
            // Parse the JWT token to get user claims
            const tokenParts = newToken.split('.');
            if (tokenParts.length === 3) {
              const payload = JSON.parse(atob(tokenParts[1]));
              const extractedUser = extractUserFromClaims(payload);
              
              // Parse custom:permissions from JWT
              if (payload['custom:permissions']) {
                try {
                  const customPermissions = JSON.parse(payload['custom:permissions']);
                  console.log('Parsed custom permissions from refreshed token:', customPermissions);
                  // Store permissions in user object
                  extractedUser.customPermissions = customPermissions;
                } catch (e) {
                  console.error('Failed to parse custom:permissions from refreshed token:', e);
                }
              }
              
              console.log('Extracted user from new token:', extractedUser);
              setUser(extractedUser);
              // Clear cache to force fresh evaluation
              permissionCache.clear();
              PermissionTokenCache.clear();
            }
          } catch (error) {
            console.error('Error extracting user from refreshed token:', error);
          }
        } else {
          // Token was cleared, reset user and ability
          console.log('Token was cleared, resetting permissions');
          setUser(null);
          setAbility(createAppAbility());
          permissionCache.clear();
          PermissionTokenCache.clear();
        }
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [isAuthenticated]);

  // Update ability when user or permission sets change
  useEffect(() => {
    console.log('Permission context effect triggered');
    console.log('isAuthenticated:', isAuthenticated);
    console.log('user:', user);
    console.log('user.customPermissions:', (user as any)?.customPermissions);
    console.log('permissionSets:', permissionSets);
    
    if (isAuthenticated && isInitialized && user) {
      try {
        // Check if we have custom permissions from JWT
        if ((user as any).customPermissions) {
          console.log('Using custom permissions from JWT, skipping permission sets API');
          // Clear the permission cache before creating a new ability
          permissionCache.clear();
          
          // Create ability using custom permissions (empty permission sets)
          const newAbility = defineAbilityFor(user, []);
          console.log('New ability created with custom permissions:', newAbility);
          setAbility(newAbility);
        } else if (permissionSets) {
          // If no custom permissions but we have permission sets from API
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
        } else if (!shouldFetchPermissions) {
          // If no custom permissions and no permission sets yet, enable fetching
          // but only if we haven't already enabled it
          console.log('No custom permissions in JWT, enabling permission sets API fetch');
          setShouldFetchPermissions(true);
        }
      } catch (error) {
        console.error('Error creating ability:', error);
        // On error, ensure we have a fallback ability
        setAbility(createAppAbility());
      }
    } else {
      // Reset ability when not authenticated
      console.log('Resetting ability - not authenticated or no user');
      setAbility(createAppAbility());
    }
  }, [isAuthenticated, isInitialized, user, permissionSets]);

  // Function to refresh permissions
  const refreshPermissions = useCallback(async () => {
    if (isAuthenticated) {
      // Enable fetching permissions from API
      setShouldFetchPermissions(true);
      // Then trigger the refetch
      await refetch();
    }
  }, [isAuthenticated, refetch, setShouldFetchPermissions]);

  // Context value
  const value = {
    ability,
    loading: isLoading || authLoading || !isInitialized,
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