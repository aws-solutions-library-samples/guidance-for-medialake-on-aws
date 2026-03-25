import { http, HttpResponse } from "msw";

/**
 * Shared MSW request handlers.
 * Add default happy-path handlers here; override per-test with server.use().
 */
export const handlers = [
  // Feature flags
  http.get("/feature-flags.json", () => {
    return HttpResponse.json({});
  }),

  // Generic API fallback — prevents unhandled request warnings for unknown routes
  http.get("/api/*", () => {
    return HttpResponse.json({ data: [] });
  }),

  http.post("/api/*", () => {
    return HttpResponse.json({ success: true });
  }),
];
