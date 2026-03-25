import React, { createContext, useCallback, useContext, useState, useEffect } from "react";
import { StorageHelper } from "../helpers/storage-helper";
import { authService } from "../../api/authService";
import { fetchAuthSession, getCurrentUser } from "aws-amplify/auth";
import { useAwsConfig } from "./aws-config-context";

interface AuthContextType {
  isAuthenticated: boolean;
  setIsAuthenticated: (isAuthenticated: boolean) => void;
  /** Call after a successful login to mark auth as complete without a loading flash. */
  completeLogin: () => void;
  checkAuthStatus: () => Promise<void>;
  /** Refresh session in the background without toggling loading state. */
  silentAuthCheck: () => Promise<void>;
  refreshSession: () => Promise<void>;
  isLoading: boolean;
  isInitialized: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Fast-path: if we already have a non-expired token in localStorage,
  // assume authenticated immediately so the UI doesn't flash a spinner.
  // The background fetchAuthSession() call will correct this if wrong.
  const hasStoredToken = () => {
    try {
      const token = StorageHelper.getToken();
      if (!token) return false;
      const parts = token.split(".");
      if (parts.length !== 3) return false;
      const payload = JSON.parse(atob(parts[1]));
      return payload.exp && payload.exp > Math.floor(Date.now() / 1000);
    } catch {
      return false;
    }
  };

  const tokenPresent = hasStoredToken();
  const [isAuthenticated, setIsAuthenticated] = useState(tokenPresent);
  const [isLoading, setIsLoading] = useState(!tokenPresent);
  const [isInitialized, setIsInitialized] = useState(tokenPresent);

  const awsConfig = useAwsConfig();

  // Core auth check logic shared by initial load and background refresh.
  // When `silent` is true the loading flag is NOT toggled, so the UI
  // keeps showing the current page instead of flashing a spinner.
  const performAuthCheck = useCallback(
    async (silent: boolean) => {
      if (!silent) {
        setIsLoading(true);
      }

      try {
        // Check if this is a SAML redirect first
        const hasSamlProvider = awsConfig?.Auth?.identity_providers.some(
          (provider) => provider.identity_provider_method === "saml"
        );

        if (
          hasSamlProvider &&
          (window.location.hash.includes("id_token") || window.location.search.includes("code="))
        ) {
          // Don't try to get current user yet, just wait for session
          try {
            const session = await fetchAuthSession();
            const token = session.tokens?.idToken?.toString();
            if (token) {
              StorageHelper.setToken(token);
              setIsAuthenticated(true);
            } else {
              setIsAuthenticated(false);
              StorageHelper.clearToken();
            }
          } catch (samlError) {
            setIsAuthenticated(false);
            StorageHelper.clearToken();
          }
        } else {
          // Not a SAML redirect, proceed with normal auth check
          try {
            const session = await fetchAuthSession();
            const token = session.tokens?.idToken?.toString();
            if (token) {
              StorageHelper.setToken(token);
              setIsAuthenticated(true);
              // Only try to get user after we have a valid token
              try {
                await getCurrentUser();
              } catch (_userError) {
                // Silent fail
              }
            } else {
              setIsAuthenticated(false);
              StorageHelper.clearToken();
            }
          } catch (error) {
            setIsAuthenticated(false);
            StorageHelper.clearToken();
          }
        }
      } catch (error) {
        setIsAuthenticated(false);
        StorageHelper.clearToken();
      } finally {
        if (!silent) {
          setIsLoading(false);
        }
        setIsInitialized(true);
      }
    },
    [awsConfig]
  );

  // Full auth check that shows loading state — used only on initial mount.
  const checkAuthStatus = useCallback(async () => {
    await performAuthCheck(false);
  }, [performAuthCheck]);

  // Silent auth check that refreshes the session in the background
  // without toggling loading state. Use this for tab-return / visibility
  // change scenarios so the UI doesn't flash a spinner.
  const silentAuthCheck = useCallback(async () => {
    await performAuthCheck(true);
  }, [performAuthCheck]);

  const refreshSession = useCallback(async () => {
    try {
      const token = await authService.refreshToken();
      if (token) {
        setIsAuthenticated(true);
      } else {
        setIsAuthenticated(false);
        StorageHelper.clearToken();
      }
    } catch (error) {
      setIsAuthenticated(false);
      StorageHelper.clearToken();
    }
  }, []);

  // Called by the login page after storing the token. Sets all three
  // flags atomically so ProtectedRoute / PermissionGuard never see a
  // partial state and flash a spinner.
  const completeLogin = useCallback(() => {
    setIsAuthenticated(true);
    setIsLoading(false);
    setIsInitialized(true);
  }, []);

  useEffect(() => {
    // If we fast-pathed from a stored token, run a silent background check
    // to validate the session without flashing a spinner.
    // Otherwise, run the full check with loading state.
    if (isAuthenticated && isInitialized) {
      silentAuthCheck();
    } else {
      checkAuthStatus();
    }
  }, [checkAuthStatus, silentAuthCheck]);

  const value = React.useMemo(
    () => ({
      isAuthenticated,
      setIsAuthenticated,
      completeLogin,
      checkAuthStatus,
      silentAuthCheck,
      refreshSession,
      isLoading,
      isInitialized,
    }),
    [
      isAuthenticated,
      setIsAuthenticated,
      completeLogin,
      checkAuthStatus,
      silentAuthCheck,
      refreshSession,
      isLoading,
      isInitialized,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
