import React, { useEffect, useRef } from "react";
import { useTokenRefresh } from "../hooks/useTokenRefresh";
import { useAuth } from "../common/hooks/auth-context";

/**
 * Component that manages token refresh lifecycle.
 * Handles both periodic background refresh and tab-return (visibility change) refresh.
 *
 * This component should be placed within the AuthProvider context.
 */
export const TokenRefreshManager: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { checkAndRefreshToken } = useTokenRefresh();
  const { silentAuthCheck, isAuthenticated } = useAuth();
  const refreshingRef = useRef(false);

  useEffect(() => {
    if (!isAuthenticated) return;

    const handleVisibilityChange = async () => {
      if (document.hidden || refreshingRef.current) return;

      refreshingRef.current = true;
      try {
        // silentAuthCheck calls fetchAuthSession which uses the Cognito
        // refresh token to obtain a fresh ID token and writes it to
        // StorageHelper. We must await it fully before checking expiry
        // so checkAndRefreshToken reads the *new* token, not the stale one.
        await silentAuthCheck();
        // Now that the token in storage is up-to-date, run the expiry
        // check. If silentAuthCheck already refreshed, this is a no-op.
        // If the refresh token itself expired, silentAuthCheck will have
        // cleared auth state and checkAndRefreshToken will bail out.
        await checkAndRefreshToken();
      } catch (error) {
        console.error("Error refreshing auth on tab return:", error);
      } finally {
        refreshingRef.current = false;
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isAuthenticated, silentAuthCheck, checkAndRefreshToken]);

  return <>{children}</>;
};
