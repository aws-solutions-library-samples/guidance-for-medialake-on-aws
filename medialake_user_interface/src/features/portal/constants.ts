/**
 * Portal upload constants shared by the public uploader and its question
 * renderer.
 */

/**
 * Default allowed upload content types for a portal.
 *
 * MUST mirror the server-side allow-list enforced by the portal upload handler
 * (`lambdas/api/portal_public/index.py` → `ALLOWED_CONTENT_TYPES`). The backend
 * rejects any other content type with a 400 ("Content type '...' is not
 * allowed"). Applying the same list as the client-side Uppy
 * `restrictions.allowedFileTypes` lets the uploader reject disallowed files at
 * selection time with a clear message, instead of staging them and failing the
 * presigned-URL request.
 *
 * Used only as a fallback when a portal does not declare its own
 * `allowedFileTypes`; an explicit per-portal list (a subset) takes precedence.
 *
 * Uppy accepts wildcard MIME types (e.g. `image/*`) and exact MIME types.
 */
export const PORTAL_DEFAULT_ALLOWED_FILE_TYPES: readonly string[] = [
  "audio/*",
  "video/*",
  "image/*",
  "application/x-mpegURL",
  "application/dash+xml",
  "application/mxf",
];
