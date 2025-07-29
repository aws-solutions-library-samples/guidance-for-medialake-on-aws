import { useEffect, useCallback, useRef } from "react";
import { useAuth } from "../common/hooks/auth-context";
import { authService } from "../api/authService";
import { isTokenExpiringSoon } from "../common/helpers/token-helper";
import { StorageHelper } from "../common/helpers/storage-helper";
import { logPermissionDebugInfo } from "../utils/permission-debug";

export const useTokenRefresh = () => {
  const { refreshSession, isAuthenticated, checkAuthStatus } = useAuth();
  const refreshInProgress = useRef(false);

  const checkAndRefreshToken = useCallback(async () => {
    if (!isAuthenticated || refreshInProgress.current) return;

    const token = StorageHelper.getToken();
    if (!token) return;

    try {
      // Check if token is expiring soon (5 minutes before expiry)
      if (isTokenExpiringSoon(token, 300)) {
        console.log("Token is expiring soon, refreshing...");
        refreshInProgress.current = true;

        try {
          await refreshSession();
          console.log("Token refreshed successfully");
        } catch (error) {
          console.error("Failed to refresh token:", error);
          // If refresh fails, check auth status to potentially redirect to login
          await checkAuthStatus();
        } finally {
          refreshInProgress.current = false;
        }
      }
    } catch (error) {
      console.error("Error checking token expiration:", error);
      refreshInProgress.current = false;
    }
  }, [isAuthenticated, refreshSession, checkAuthStatus]);

  useEffect(() => {
    if (!isAuthenticated) return;

    // Check immediately when component mounts
    checkAndRefreshToken();

    // Set up periodic check every 2 minutes
    const interval = setInterval(checkAndRefreshToken, 2 * 60 * 1000);

    // Check when user becomes active after being idle
    const handleUserActivity = () => {
      // Debounce activity checks to avoid excessive calls
      setTimeout(() => {
        checkAndRefreshToken();
      }, 1000);
    };

    // Listen for user activity events
    const events = ["mousedown", "keydown", "scroll", "touchstart"];
    events.forEach((event) => {
      document.addEventListener(event, handleUserActivity, { passive: true });
    });

    // Handle when user returns to the tab
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log("User returned to tab, checking token status...");
        logPermissionDebugInfo(); // Log debug info when user returns
        // Small delay to ensure any background token refresh has completed
        setTimeout(() => {
          checkAndRefreshToken();
        }, 1500);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Handle when window regains focus
    const handleFocus = () => {
      console.log("Window regained focus, checking token status...");
      setTimeout(() => {
        checkAndRefreshToken();
      }, 1000);
    };

    window.addEventListener("focus", handleFocus);

    return () => {
      clearInterval(interval);
      events.forEach((event) => {
        document.removeEventListener(event, handleUserActivity);
      });
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", handleFocus);
    };
  }, [isAuthenticated, checkAndRefreshToken]);

  // Return the manual refresh function for external use if needed
  return { checkAndRefreshToken };
};
