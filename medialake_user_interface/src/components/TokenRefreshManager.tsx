import React, { useEffect } from "react";
import { useTokenRefresh } from "../hooks/useTokenRefresh";
import { useAuth } from "../common/hooks/auth-context";

/**
 * Component that manages token refresh lifecycle
 * This component should be placed within the AuthProvider context
 */
export const TokenRefreshManager: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { checkAndRefreshToken } = useTokenRefresh();
  const { checkAuthStatus, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) return;

    // Handle page visibility changes specifically for token refresh
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log(
          "Page became visible, refreshing auth status and checking token...",
        );
        // When user returns to page, check auth status first, then token
        checkAuthStatus()
          .then(() => {
            // Small delay to ensure auth status check completes
            setTimeout(() => {
              checkAndRefreshToken();
            }, 500);
          })
          .catch((error) => {
            console.error(
              "Error checking auth status on visibility change:",
              error,
            );
          });
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isAuthenticated, checkAuthStatus, checkAndRefreshToken]);

  return <>{children}</>;
};
