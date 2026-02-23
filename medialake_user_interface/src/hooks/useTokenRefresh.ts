import { useEffect, useCallback, useRef } from "react";
import { useAuth } from "../common/hooks/auth-context";
import { isTokenExpiringSoon } from "../common/helpers/token-helper";
import { StorageHelper } from "../common/helpers/storage-helper";

export const useTokenRefresh = () => {
  const { refreshSession, isAuthenticated, silentAuthCheck } = useAuth();
  const refreshInProgress = useRef(false);

  const checkAndRefreshToken = useCallback(async () => {
    if (!isAuthenticated || refreshInProgress.current) return;

    const token = StorageHelper.getToken();
    if (!token) return;

    try {
      // Check if token is expiring soon (5 minutes before expiry)
      if (isTokenExpiringSoon(token, 300)) {
        refreshInProgress.current = true;

        try {
          await refreshSession();
        } catch (error) {
          console.error("Failed to refresh token:", error);
          // Silent check — don't flash a loading spinner
          await silentAuthCheck();
        } finally {
          refreshInProgress.current = false;
        }
      }
    } catch (error) {
      console.error("Error checking token expiration:", error);
      refreshInProgress.current = false;
    }
  }, [isAuthenticated, refreshSession, silentAuthCheck]);

  useEffect(() => {
    if (!isAuthenticated) return;

    // Check immediately when component mounts
    checkAndRefreshToken();

    // Set up periodic check every 4 minutes
    const interval = setInterval(checkAndRefreshToken, 4 * 60 * 1000);

    return () => {
      clearInterval(interval);
    };
  }, [isAuthenticated, checkAndRefreshToken]);

  return { checkAndRefreshToken };
};
