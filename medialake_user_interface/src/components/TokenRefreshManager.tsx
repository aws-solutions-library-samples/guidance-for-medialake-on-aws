import React, { useEffect } from "react";
import { useTokenRefresh } from "../hooks/useTokenRefresh";
import { useAuth } from "../common/hooks/auth-context";

/**
 * Component that manages token refresh lifecycle
 * This component should be placed within the AuthProvider context
 */
export const TokenRefreshManager: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { checkAndRefreshToken } = useTokenRefresh();
  const { silentAuthCheck, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) return;

    // Handle page visibility changes specifically for token refresh
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log("Page became visible, silently refreshing auth and checking token...");
        // Use silent check so the UI doesn't flash a loading spinner
        silentAuthCheck()
          .then(() => {
            checkAndRefreshToken();
          })
          .catch((error) => {
            console.error("Error checking auth status on visibility change:", error);
          });
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isAuthenticated, silentAuthCheck, checkAndRefreshToken]);

  return <>{children}</>;
};
