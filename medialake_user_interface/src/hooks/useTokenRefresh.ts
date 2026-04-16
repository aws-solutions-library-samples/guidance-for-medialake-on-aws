import { useEffect, useCallback, useRef } from "react";
import { useAuth } from "../common/hooks/auth-context";
import { isTokenExpiringSoon } from "../common/helpers/token-helper";
import { StorageHelper } from "../common/helpers/storage-helper";

// How often to check token expiry (4 minutes).
const CHECK_INTERVAL_MS = 4 * 60 * 1000;

// Refresh when the token has less than 5 minutes left.
const REFRESH_BUFFER_SECONDS = 300;

export const useTokenRefresh = () => {
  const { refreshSession, isAuthenticated, silentAuthCheck } = useAuth();
  const refreshInProgress = useRef(false);

  const checkAndRefreshToken = useCallback(async () => {
    if (!isAuthenticated || refreshInProgress.current) return;

    const token = StorageHelper.getToken();
    if (!token) return;

    try {
      if (isTokenExpiringSoon(token, REFRESH_BUFFER_SECONDS)) {
        refreshInProgress.current = true;

        try {
          await refreshSession();
        } catch (error) {
          console.error("Failed to refresh token:", error);
          // Fallback: silentAuthCheck uses Amplify's fetchAuthSession which
          // will attempt the refresh via the Cognito refresh token.
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

    // Check immediately on mount
    checkAndRefreshToken();

    // Use a self-correcting timer instead of setInterval.
    // Browsers throttle setInterval in background tabs (Chrome suspends
    // them entirely after ~5 min). When the tab wakes up, a plain
    // setInterval may not fire for a long time. By scheduling each
    // iteration with setTimeout and checking the *actual* elapsed time,
    // we can detect that we were suspended and refresh immediately.
    let timerId: ReturnType<typeof setTimeout>;
    let lastCheck = Date.now();

    const scheduleNext = () => {
      timerId = setTimeout(async () => {
        const elapsed = Date.now() - lastCheck;
        lastCheck = Date.now();

        // If more time passed than expected (tab was suspended), the token
        // may have expired or be close to expiry — always check.
        if (elapsed > CHECK_INTERVAL_MS * 1.5) {
          // Tab was likely suspended. Force a refresh attempt.
          refreshInProgress.current = false; // Reset in case it was stuck
        }

        await checkAndRefreshToken();
        scheduleNext();
      }, CHECK_INTERVAL_MS);
    };

    scheduleNext();

    return () => {
      clearTimeout(timerId);
    };
  }, [isAuthenticated, checkAndRefreshToken]);

  return { checkAndRefreshToken };
};
