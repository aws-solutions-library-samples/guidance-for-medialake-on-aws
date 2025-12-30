import React, { createContext, useCallback, useContext, useState, useEffect } from "react";
import { StorageHelper } from "../helpers/storage-helper";
import { authService } from "../../api/authService";
import { fetchAuthSession, getCurrentUser } from "aws-amplify/auth";
import { useAwsConfig } from "./aws-config-context";

interface AuthContextType {
  isAuthenticated: boolean;
  setIsAuthenticated: (isAuthenticated: boolean) => void;
  checkAuthStatus: () => Promise<void>;
  refreshSession: () => Promise<void>;
  isLoading: boolean;
  isInitialized: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false);

  const awsConfig = useAwsConfig();

  const checkAuthStatus = useCallback(async () => {
    setIsLoading(true);

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
      setIsLoading(false);
      setIsInitialized(true);
    }
  }, [awsConfig]);

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

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const value = {
    isAuthenticated,
    setIsAuthenticated,
    checkAuthStatus,
    refreshSession,
    isLoading,
    isInitialized,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
