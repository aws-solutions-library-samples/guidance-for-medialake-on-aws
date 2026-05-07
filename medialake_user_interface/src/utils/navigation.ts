/**
 * Navigation utility for programmatic navigation outside of React components.
 * This is used by the axios interceptor to redirect to the access-denied page.
 */

import { router } from "@/routes/router";

/**
 * Navigate to a route programmatically without a full page reload.
 * This uses the router instance directly, which works outside of React components.
 *
 * @param path - The path to navigate to
 */
export const navigateTo = (path: string) => {
  router.navigate(path);
};

/**
 * Navigate to the access-denied page with error details.
 *
 * @param errorDetails - Error details to store in sessionStorage
 */
export const navigateToAccessDenied = (errorDetails: {
  message: string;
  requiredPermission?: string;
  attemptedUrl?: string;
  timestamp: string;
}) => {
  // Store error details in sessionStorage for the access-denied page to display
  sessionStorage.setItem("accessDeniedError", JSON.stringify(errorDetails));

  // Navigate using the router instance
  router.navigate("/access-denied");
};
