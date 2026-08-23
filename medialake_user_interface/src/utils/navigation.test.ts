/**
 * Tests for navigateToAccessDenied.
 *
 * Regression cover for the access-denied trap: a 403 used to PUSH
 * /access-denied unconditionally, so
 *   - a page with several permission-gated queries stacked one history entry
 *     per 403, and "Go Back" stepped onto another copy of /access-denied; and
 *   - a 403 resolving after the user clicked "Go to Home" or edited the URL
 *     (the interceptor reaches this helper via a dynamic import, so the
 *     redirect lands a tick late) dragged them straight back.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const navigate = vi.fn();

// Mocked before importing the module under test so the singleton is the mock.
vi.mock("@/routes/router", () => ({
  router: {
    navigate: (...args: unknown[]) => navigate(...args),
    state: {
      get location() {
        return { pathname: routerPathname };
      },
    },
  },
}));

let routerPathname = "/";

const { ACCESS_DENIED_ROUTE, navigateToAccessDenied } = await import("./navigation");

/** Point both the router and window.location at the same route. */
const setRoute = (pathname: string) => {
  routerPathname = pathname;
  window.history.replaceState({}, "", pathname);
};

const details = {
  message: "You don't have permission to perform this action",
  requiredPermission: "assets:view",
  attemptedUrl: "/assets",
  timestamp: "2026-08-01T00:00:00.000Z",
};

describe("navigateToAccessDenied", () => {
  beforeEach(() => {
    navigate.mockClear();
    sessionStorage.clear();
    setRoute("/assets");
  });

  it("navigates to the access-denied route", () => {
    navigateToAccessDenied(details);

    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(ACCESS_DENIED_ROUTE, { replace: true });
  });

  it("replaces rather than pushes, so denials cannot stack in history", () => {
    navigateToAccessDenied(details);

    expect(navigate).toHaveBeenCalledWith(
      ACCESS_DENIED_ROUTE,
      expect.objectContaining({ replace: true })
    );
  });

  it("stores the error details for the page to render", () => {
    navigateToAccessDenied(details);

    expect(JSON.parse(sessionStorage.getItem("accessDeniedError")!)).toEqual(details);
  });

  describe("guard 1: already on the access-denied route", () => {
    it("does not navigate again", () => {
      setRoute(ACCESS_DENIED_ROUTE);

      navigateToAccessDenied(details);

      expect(navigate).not.toHaveBeenCalled();
    });

    it("does not overwrite the details the page is already showing", () => {
      setRoute(ACCESS_DENIED_ROUTE);

      navigateToAccessDenied(details);

      expect(sessionStorage.getItem("accessDeniedError")).toBeNull();
    });

    it("suppresses every extra 403 from a page that mounts several queries", () => {
      // First 403 redirects...
      navigateToAccessDenied(details, "/assets");
      expect(navigate).toHaveBeenCalledTimes(1);

      // ...and the app is now on /access-denied, so the rest are no-ops.
      setRoute(ACCESS_DENIED_ROUTE);
      navigateToAccessDenied(details, "/assets");
      navigateToAccessDenied(details, "/assets");
      navigateToAccessDenied(details, "/assets");

      expect(navigate).toHaveBeenCalledTimes(1);
    });
  });

  describe("guard 2: stale 403 from a route the user already left", () => {
    it("does not hijack a navigation the user already made", () => {
      // 403 was issued while on /assets; user has since reached Home.
      setRoute("/");

      navigateToAccessDenied(details, "/assets");

      expect(navigate).not.toHaveBeenCalled();
    });

    it("still redirects when the user is on the route that failed", () => {
      setRoute("/assets");

      navigateToAccessDenied(details, "/assets");

      expect(navigate).toHaveBeenCalledWith(ACCESS_DENIED_ROUTE, { replace: true });
    });

    it("treats a different route param as a different route", () => {
      setRoute("/assets/456");

      navigateToAccessDenied(details, "/assets/123");

      expect(navigate).not.toHaveBeenCalled();
    });

    it("ignores the query string, since it is the same page", () => {
      routerPathname = "/search";
      window.history.replaceState({}, "", "/search?q=updated");

      navigateToAccessDenied(details, "/search");

      expect(navigate).toHaveBeenCalledWith(ACCESS_DENIED_ROUTE, { replace: true });
    });

    it("redirects when no origin path is supplied", () => {
      setRoute("/somewhere-else");

      navigateToAccessDenied(details);

      expect(navigate).toHaveBeenCalledWith(ACCESS_DENIED_ROUTE, { replace: true });
    });

    it("honours an empty-string origin path rather than treating it as absent", () => {
      setRoute("/assets");

      navigateToAccessDenied(details, "");

      expect(navigate).not.toHaveBeenCalled();
    });
  });
});
