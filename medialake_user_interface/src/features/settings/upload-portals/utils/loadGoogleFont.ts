/**
 * Idempotent Google Fonts CDN loader.
 *
 * Injects a single `<link rel="stylesheet">` element per font family into
 * `document.head`, pointing at the Google Fonts CSS2 endpoint. Subsequent
 * calls for the same family are no-ops so the DOM never accumulates duplicate
 * link tags (see Property 7 in design.md).
 *
 * System-font stacks (`"System Default"`, `-apple-system*`, empty/falsy
 * strings) bypass the CDN entirely — we never emit a request for a family
 * the browser already resolves locally.
 *
 * SSR-safe: in environments where `document` is undefined the function
 * returns early without throwing.
 */

/**
 * Prefix applied to every link element's `id` so we can identify / clean up
 * font links from tests, hot-reload, etc.
 */
export const GOOGLE_FONT_LINK_ID_PREFIX = "google-font-";

/**
 * Font weight range loaded for every family. Matches the weights used by the
 * typography controls (400, 500, 600, 700, 800, 900).
 */
const FONT_WEIGHT_RANGE = "400;500;600;700;800;900";

/**
 * Returns `true` when `fontFamily` should NOT trigger a Google Fonts request.
 *
 * System stacks include:
 * - `"System Default"` (curated list sentinel)
 * - any family starting with `-apple-system` (the native iOS/macOS stack)
 * - empty strings and other falsy inputs
 */
export function isSystemFontStack(fontFamily: string | null | undefined): boolean {
  if (!fontFamily) {
    return true;
  }
  if (fontFamily === "System Default") {
    return true;
  }
  if (fontFamily.startsWith("-apple-system")) {
    return true;
  }
  return false;
}

/**
 * Slugify a font family into a DOM-safe id suffix.
 *
 * Lowercases the input and replaces every run of non-alphanumeric characters
 * with a single hyphen; leading/trailing hyphens are trimmed. Example:
 * `"Plus Jakarta Sans"` → `"plus-jakarta-sans"`.
 */
function slugifyFontFamily(fontFamily: string): string {
  return fontFamily
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Build the Google Fonts CSS2 URL for a font family.
 *
 * Google Fonts traditionally encodes spaces as `+`, so we percent-encode via
 * `encodeURIComponent` (which handles every other special character safely)
 * then swap `%20` for `+` to match the canonical URL form.
 *
 * The resulting URL includes all six weights (400-900) and `display=swap`
 * so the browser paints fallback text immediately while the font loads.
 */
export function buildGoogleFontHref(fontFamily: string): string {
  const family = encodeURIComponent(fontFamily).replace(/%20/g, "+");
  return `https://fonts.googleapis.com/css2?family=${family}:wght@${FONT_WEIGHT_RANGE}&display=swap`;
}

/**
 * Build the `id` attribute for a font family's `<link>` element. Exposed
 * internally so the idempotence check uses the exact same string.
 */
function buildLinkId(fontFamily: string): string {
  return `${GOOGLE_FONT_LINK_ID_PREFIX}${slugifyFontFamily(fontFamily)}`;
}

/**
 * Inject a Google Fonts `<link rel="stylesheet">` for `fontFamily` into
 * `document.head` — once.
 *
 * Contract:
 * - No-op when `fontFamily` is a system stack (see {@link isSystemFontStack}).
 * - No-op when `document` is undefined (SSR).
 * - No-op when a link with the computed id already exists.
 * - Otherwise creates exactly one `<link rel="stylesheet">` with a stable
 *   `id` (prefixed `google-font-`) and appends it to `document.head`.
 */
export function loadGoogleFont(fontFamily: string): void {
  if (isSystemFontStack(fontFamily)) {
    return;
  }

  if (typeof document === "undefined") {
    // SSR / non-DOM environment — nothing to inject into.
    return;
  }

  const id = buildLinkId(fontFamily);
  if (!id || id === GOOGLE_FONT_LINK_ID_PREFIX) {
    // Slug collapsed to empty (e.g., input of only punctuation). Refuse to
    // create an unidentifiable link element.
    return;
  }

  if (document.getElementById(id)) {
    // Already loaded — preserve idempotence (Property 7).
    return;
  }

  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = buildGoogleFontHref(fontFamily);
  document.head.appendChild(link);
}
