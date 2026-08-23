/**
 * Navigation utility for programmatic navigation outside of React components.
 * This is used by the axios interceptor to redirect to the access-denied page.
 */

import { router } from "@/routes/router";

/** Route that renders AccessDeniedPage. Declared in @/routes/router. */
export const ACCESS_DENIED_ROUTE = "/access-denied";

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
 * Two guards keep a 403 from trapping the user on this page:
 *
 * 1. If the app is already showing the access-denied route, do nothing. A page
 *    that mounts several permission-gated queries produces one 403 per query,
 *    and each one used to append its own history entry — so "Go Back" simply
 *    stepped onto another copy of /access-denied.
 *
 * 2. If `originPath` is supplied and the app has since moved elsewhere, do
 *    nothing. The caller reaches this function through a dynamic import, so a
 *    403 can resolve *after* the user has clicked "Go to Home" or edited the
 *    URL; the late redirect then dragged them straight back.
 *
 * The navigation itself uses `replace` so repeated denials cannot accumulate
 * history entries and strand the user.
 *
 * @param errorDetails - Error details for the access-denied page to display
 * @param originPath - `window.location.pathname` captured by the caller at the
 *   moment the request failed, before any async hop. Omit to always redirect.
 */
export const navigateToAccessDenied = (
  errorDetails: {
    message: string;
    requiredPermission?: string;
    attemptedUrl?: string;
    timestamp: string;
  },
  originPath?: string
) => {
  // Guard 1 — compared in route space (basename-stripped), which is the space
  // ACCESS_DENIED_ROUTE is declared in.
  if (router.state.location.pathname === ACCESS_DENIED_ROUTE) {
    return;
  }

  // Guard 2 — compared in URL space. `originPath` comes from window.location,
  // so read the current value from the same source to keep the comparison
  // consistent under any basename. React Router updates window.location
  // synchronously via pushState/replaceState, so this always reflects the route
  // currently on screen.
  if (originPath !== undefined && window.location.pathname !== originPath) {
    return;
  }

  // Store error details in sessionStorage for the access-denied page to display
  sessionStorage.setItem("accessDeniedError", JSON.stringify(errorDetails));

  // Replace rather than push: a denial should not add a history entry the user
  // has to click back through.
  router.navigate(ACCESS_DENIED_ROUTE, { replace: true });
};
