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

  // Synchronous fast-path: if we have a valid token and cached permissions,
  // initialize immediately so the UI never shows a loading spinner.
  const initFromCache = (): {
    user: User | null;
    ability: AppAbility;
    initialized: boolean;
  } => {
    try {
      const token = StorageHelper.getToken();
      if (!token) return { user: null, ability: createAppAbility(), initialized: false };

      const globalCache = globalPermissionCache.getGlobalCache(token);
      if (globalCache) {
        const cachedUser = {
          ...globalCache.user,
          customPermissions: globalCache.customPermissions,
        };
        return { user: cachedUser, ability: globalCache.ability, initialized: true };
      }

      // No cache but we have a token — parse it synchronously
      const parts = token.split(".");
      if (parts.length !== 3)
        return { user: null, ability: createAppAbility(), initialized: false };

      const payload = JSON.parse(atob(parts[1]));
      if (!payload.exp || payload.exp <= Math.floor(Date.now() / 1000)) {
        return { user: null, ability: createAppAbility(), initialized: false };
      }

      const extractedUser = extractUserFromClaims(payload);
      if (payload["custom:permissions"]) {
        try {
          extractedUser.customPermissions = JSON.parse(payload["custom:permissions"]);
        } catch {
          // ignore parse errors
        }
      }

      const newAbility = defineAbilityFor(extractedUser, []);

      // Populate the global cache for future reads
      const expiresIn = payload.exp - Math.floor(Date.now() / 1000);
      if (expiresIn > 0) {
        globalPermissionCache.setGlobalCache(
          extractedUser,
          extractedUser.customPermissions || [],
          newAbility,
          [],
          token,
          expiresIn
        );
      }

      return { user: extractedUser, ability: newAbility, initialized: true };
    } catch {
      return { user: null, ability: createAppAbility(), initialized: false };
    }
  };

  const cachedRef = React.useRef<ReturnType<typeof initFromCache> | null>(null);
  if (!cachedRef.current) {
    cachedRef.current = initFromCache();
  }
  const cached = cachedRef.current;
  const [user, setUser] = useState<User | null>(cached.user);
  const [ability, setAbility] = useState<AppAbility>(() => cached.ability);
  const [permissionsInitialized, setPermissionsInitialized] = useState(cached.initialized);

  // Extract user information from JWT token and check global cache
  useEffect(() => {
    if (isAuthenticated && isInitialized) {
      try {
        const token = StorageHelper.getToken();
        if (token) {
          // Check global cache first
          const globalCache = globalPermissionCache.getGlobalCache(token);
          if (globalCache) {
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

            const extractedUser = extractUserFromClaims(payload);
            let customPermissions: string[] = [];

            // Parse custom:permissions from JWT
            if (payload["custom:permissions"]) {
              try {
                customPermissions = JSON.parse(payload["custom:permissions"]);
                // Store permissions in user object
                extractedUser.customPermissions = customPermissions;
              } catch (e) {
                console.error("Failed to parse custom:permissions:", e);
              }
            }

            setUser(extractedUser);
          } else {
            console.error("Invalid JWT token format");
            setUser(null);
          }
        } else {
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

  // Listen for storage changes (token updates) to refresh permissions.
  // StorageEvent only fires for cross-tab changes, so we also patch
  // StorageHelper.setToken to detect same-tab token refreshes.
  useEffect(() => {
    if (!isAuthenticated) return;

    const handleTokenChange = (newToken: string | null) => {
      if (newToken) {
        try {
          const tokenParts = newToken.split(".");
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            const extractedUser = extractUserFromClaims(payload);

            if (payload["custom:permissions"]) {
              try {
                const customPermissions = JSON.parse(payload["custom:permissions"]);
                extractedUser.customPermissions = customPermissions;
              } catch (e) {
                console.error("Failed to parse custom:permissions from refreshed token:", e);
              }
            }

            setUser(extractedUser);

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
        setUser(null);
        setAbility(createAppAbility());
        globalPermissionCache.clear();
      }
    };

    // Cross-tab changes via StorageEvent
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "medialake-auth-token" && e.newValue !== e.oldValue) {
        handleTokenChange(e.newValue);
      }
    };

    window.addEventListener("storage", handleStorageChange);

    // Same-tab changes: monkey-patch localStorage.setItem to detect token writes
    // StorageEvent does NOT fire for same-tab writes, so this is necessary
    const originalSetItem = localStorage.setItem.bind(localStorage);
    const currentToken = StorageHelper.getToken();
    let lastKnownToken = currentToken;

    localStorage.setItem = function (key: string, value: string) {
      originalSetItem(key, value);
      if (key === "medialake-auth-token" && value !== lastKnownToken) {
        lastKnownToken = value;
        handleTokenChange(value);
      }
    };

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      // Restore original setItem
      localStorage.setItem = originalSetItem;
    };
  }, [isAuthenticated]);

  // Update ability when user changes
  useEffect(() => {
    if (isAuthenticated && isInitialized && user) {
      try {
        const token = StorageHelper.getToken();
        if (!token) return;

        // Check if we already have this in global cache
        const globalCache = globalPermissionCache.getGlobalCache(token);
        if (globalCache && globalCache.user.id === user.id) {
          setAbility(globalCache.ability);
          setPermissionsInitialized(true);
          return;
        }

        // Create ability using custom permissions from JWT (or empty if none)
        const newAbility = defineAbilityFor(user, []);
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

  // Context value — memoized to prevent unnecessary re-renders of all permission consumers
  const value = React.useMemo(
    () => ({
      ability,
      loading: authLoading || !isInitialized || (isAuthenticated && !permissionsInitialized),
      error: null,
      refreshPermissions,
    }),
    [
      ability,
      authLoading,
      isInitialized,
      isAuthenticated,
      permissionsInitialized,
      refreshPermissions,
    ]
  );

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
