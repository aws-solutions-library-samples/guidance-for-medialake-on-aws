import React, {
  createContext,
  useCallback,
  useContext,
  useState,
  useEffect,
} from "react";
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

export const AuthContext = createContext<AuthContextType | undefined>(
  undefined,
);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false);

  const awsConfig = useAwsConfig();

  const checkAuthStatus = useCallback(async () => {
    console.log("AuthContext: Starting auth status check...");
    setIsLoading(true);

    try {
      // Check if this is a SAML redirect first
      const hasSamlProvider = awsConfig?.Auth?.identity_providers.some(
        (provider) => provider.identity_provider_method === "saml",
      );

      if (
        hasSamlProvider &&
        (window.location.hash.includes("id_token") ||
          window.location.search.includes("code="))
      ) {
        console.log("Detected SAML redirect, waiting for session...");
        // Don't try to get current user yet, just wait for session
        try {
          const session = await fetchAuthSession();
          console.log("Got session after SAML redirect:", session);
          const token = session.tokens?.idToken?.toString();
          if (token) {
            console.log("=== SAML Redirect Token ===");
            const tokenParts = token.split(".");
            if (tokenParts.length === 3) {
              const payload = JSON.parse(atob(tokenParts[1]));
              console.log("Token claims:", JSON.stringify(payload, null, 2));
              console.log("cognito:groups:", payload["cognito:groups"]);
              console.log("custom:permissions:", payload["custom:permissions"]);
            }

            StorageHelper.setToken(token);
            setIsAuthenticated(true);
          } else {
            setIsAuthenticated(false);
            StorageHelper.clearToken();
          }
        } catch (samlError) {
          console.error("Failed to handle SAML redirect:", samlError);
          setIsAuthenticated(false);
          StorageHelper.clearToken();
        }
      } else {
        // Not a SAML redirect, proceed with normal auth check
        try {
          const session = await fetchAuthSession();
          console.log("Auth session:", session);
          const token = session.tokens?.idToken?.toString();
          if (token) {
            console.log("=== Regular Auth Token ===");
            const tokenParts = token.split(".");
            if (tokenParts.length === 3) {
              const payload = JSON.parse(atob(tokenParts[1]));
              console.log("Token claims:", JSON.stringify(payload, null, 2));
              console.log("cognito:groups:", payload["cognito:groups"]);
              console.log("custom:permissions:", payload["custom:permissions"]);
            }
            console.log("========================");
            StorageHelper.setToken(token);
            setIsAuthenticated(true);
            // Only try to get user after we have a valid token
            try {
              const user = await getCurrentUser();
              console.log("Current user:", user);
            } catch (userError) {
              console.log(
                "Could not get user but have valid token:",
                userError,
              );
            }
          } else {
            console.log("No valid token found, user is not authenticated");
            setIsAuthenticated(false);
            StorageHelper.clearToken();
          }
        } catch (error) {
          console.log("No valid session:", error);
          setIsAuthenticated(false);
          StorageHelper.clearToken();
        }
      }
    } catch (error) {
      console.error("Auth status check failed:", error);
      setIsAuthenticated(false);
      StorageHelper.clearToken();
    } finally {
      console.log("AuthContext: Auth status check completed");
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
      console.error("Session refresh failed:", error);
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
