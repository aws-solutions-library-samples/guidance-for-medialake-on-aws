// src/permissions/context/permission-context.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { AppAbility, createAppAbility } from "../types/ability.types";
import { PermissionContextType, User } from "../types/permission.types";
import { defineAbilityFor, extractUserFromClaims } from "../utils/ability-factory";
import { useAuth } from "../../common/hooks/auth-context";
import { StorageHelper } from "../../common/helpers/storage-helper";
import { globalPermissionCache } from "../utils/global-permission-cache";

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
  const [permissionsInitialized, setPermissionsInitialized] = useState(false);

  // Extract user information from JWT token and check global cache
  useEffect(() => {
    console.log("PermissionProvider: Auth state changed", {
      isAuthenticated,
      isInitialized,
      authLoading,
    });

    if (isAuthenticated && isInitialized) {
      try {
        const token = StorageHelper.getToken();
        if (token) {
          // Check global cache first
          const globalCache = globalPermissionCache.getGlobalCache(token);
          if (globalCache) {
            console.log("Using global cached user and permissions");
            const cachedUser = {
              ...globalCache.user,
              customPermissions: globalCache.customPermissions,
            };
            setUser(cachedUser);
            setAbility(globalCache.ability);
            setPermissionsInitialized(true);
            return;
          }

          // Parse the JWT token to get user claims
          const tokenParts = token.split(".");
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            console.log("=== JWT Token Claims ===");
            console.log("Full token payload:", JSON.stringify(payload, null, 2));
            console.log("cognito:groups claim:", payload["cognito:groups"]);
            console.log("custom:permissions claim:", payload["custom:permissions"]);
            console.log("cognito:username claim:", payload["cognito:username"]);
            console.log("sub claim:", payload.sub);
            console.log("email claim:", payload.email);
            console.log("======================");

            const extractedUser = extractUserFromClaims(payload);
            let customPermissions: string[] = [];

            // Parse custom:permissions from JWT
            if (payload["custom:permissions"]) {
              try {
                customPermissions = JSON.parse(payload["custom:permissions"]);
                console.log("Parsed custom permissions:", customPermissions);
                // Store permissions in user object
                extractedUser.customPermissions = customPermissions;
              } catch (e) {
                console.error("Failed to parse custom:permissions:", e);
              }
            }

            console.log("Extracted user from claims:", extractedUser);
            setUser(extractedUser);
          } else {
            console.error("Invalid JWT token format");
            setUser(null);
          }
        } else {
          console.log("No token found");
          setUser(null);
        }
      } catch (error) {
        console.error("Error extracting user from token:", error);
        setUser(null);
      }
    } else {
      setUser(null);
      setPermissionsInitialized(false);
      globalPermissionCache.clear(); // Clear cache on logout
    }
  }, [isAuthenticated, isInitialized]);

  // Listen for storage changes (token updates) to refresh permissions
  useEffect(() => {
    if (!isAuthenticated) return;

    const handleStorageChange = (e: StorageEvent) => {
      // Handle token changes in storage
      if (e.key === "medialake-auth-token" && e.newValue !== e.oldValue) {
        console.log("Token changed in storage, refreshing permissions...");

        const newToken = e.newValue;
        if (newToken) {
          try {
            // Parse the JWT token to get user claims
            const tokenParts = newToken.split(".");
            if (tokenParts.length === 3) {
              const payload = JSON.parse(atob(tokenParts[1]));
              const extractedUser = extractUserFromClaims(payload);

              // Parse custom:permissions from JWT
              if (payload["custom:permissions"]) {
                try {
                  const customPermissions = JSON.parse(payload["custom:permissions"]);
                  console.log("Parsed custom permissions from refreshed token:", customPermissions);
                  // Store permissions in user object
                  extractedUser.customPermissions = customPermissions;
                } catch (e) {
                  console.error("Failed to parse custom:permissions from refreshed token:", e);
                }
              }

              console.log("Extracted user from new token:", extractedUser);
              setUser(extractedUser);

              // Update token in global cache instead of clearing everything
              const exp = payload.exp;
              if (exp) {
                const expiresIn = exp - Math.floor(Date.now() / 1000);
                if (expiresIn > 0) {
                  globalPermissionCache.updateToken(newToken, expiresIn);
                }
              }
            }
          } catch (error) {
            console.error("Error extracting user from refreshed token:", error);
          }
        } else {
          // Token was cleared, reset user and ability
          console.log("Token was cleared, resetting permissions");
          setUser(null);
          setAbility(createAppAbility());
          globalPermissionCache.clear();
        }
      }
    };

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [isAuthenticated]);

  // Update ability when user changes
  useEffect(() => {
    console.log("Permission context effect triggered");
    console.log("isAuthenticated:", isAuthenticated);
    console.log("user:", user);
    console.log("user.customPermissions:", (user as any)?.customPermissions);

    if (isAuthenticated && isInitialized && user) {
      try {
        const token = StorageHelper.getToken();
        if (!token) return;

        // Check if we already have this in global cache
        const globalCache = globalPermissionCache.getGlobalCache(token);
        if (globalCache && globalCache.user.id === user.id) {
          console.log("Using existing global cache for ability");
          setAbility(globalCache.ability);
          setPermissionsInitialized(true);
          return;
        }

        // Create ability using custom permissions from JWT (or empty if none)
        const newAbility = defineAbilityFor(user, []);
        console.log("New ability created:", newAbility);
        setAbility(newAbility);
        setPermissionsInitialized(true);

        // Store in global cache
        const exp = JSON.parse(atob(token.split(".")[1])).exp;
        const expiresIn = exp - Math.floor(Date.now() / 1000);
        if (expiresIn > 0) {
          globalPermissionCache.setGlobalCache(
            user,
            (user as any)?.customPermissions || [],
            newAbility,
            [],
            token,
            expiresIn
          );
        }
      } catch (error) {
        console.error("Error creating ability:", error);
        // On error, ensure we have a fallback ability
        setAbility(createAppAbility());
        setPermissionsInitialized(true); // Set to true to prevent infinite loading
      }
    } else if (!isAuthenticated) {
      // Reset ability when not authenticated
      console.log("Resetting ability - not authenticated or no user");
      setAbility(createAppAbility());
      setPermissionsInitialized(false);
    }
  }, [isAuthenticated, isInitialized, user]);

  // Function to refresh permissions (re-reads from JWT)
  const refreshPermissions = useCallback(async () => {
    if (isAuthenticated) {
      // Force re-read from JWT by clearing cache and re-triggering the user effect
      globalPermissionCache.clear();
      setPermissionsInitialized(false);
      // Re-extract user from token to trigger the ability update
      try {
        const token = StorageHelper.getToken();
        if (token) {
          const tokenParts = token.split(".");
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            const extractedUser = extractUserFromClaims(payload);
            if (payload["custom:permissions"]) {
              try {
                extractedUser.customPermissions = JSON.parse(payload["custom:permissions"]);
              } catch (e) {
                console.error("Failed to parse custom:permissions:", e);
              }
            }
            setUser(extractedUser);
          }
        }
      } catch (error) {
        console.error("Error refreshing permissions:", error);
      }
    }
  }, [isAuthenticated]);

  // Context value - ensure we stay in loading state until permissions are fully initialized
  const value = {
    ability,
    loading: authLoading || !isInitialized || (isAuthenticated && !permissionsInitialized),
    error: null,
    refreshPermissions,
  };

  return <PermissionContext.Provider value={value}>{children}</PermissionContext.Provider>;
}

/**
 * Hook to use the permission context
 * @returns The permission context
 */
export function usePermissionContext() {
  const context = useContext(PermissionContext);
  if (context === undefined) {
    throw new Error("usePermissionContext must be used within a PermissionProvider");
  }
  return context;
}
