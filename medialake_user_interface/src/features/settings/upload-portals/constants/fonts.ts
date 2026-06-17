/**
 * Curated font list for the portal visual editor typography section.
 *
 * Each entry's `family` is what gets stored on the `PortalAppearance` and
 * passed to `loadGoogleFont`. `"System Default"` is a sentinel that the
 * loader treats as a no-op; the `fallback` stack is used by
 * `createPortalTheme` when assembling MUI `typography.fontFamily`.
 *
 * The curated set is intentionally small to keep the font picker scannable.
 * Every entry except System Default is a Google Font, so `loadGoogleFont`
 * can fetch any of them from the CDN by name without extra metadata.
 */

export interface PortalFontOption {
  /**
   * Canonical family name. Stored verbatim on
   * `appearance.typography.headingFontFamily` / `bodyFontFamily`, and used
   * as the URL parameter when building the Google Fonts CSS request.
   */
  family: string;
  /**
   * CSS fallback stack appended to the family when constructing
   * `font-family`. `"System Default"` uses the system-ui stack and is the
   * only entry whose family is not a Google Font.
   */
  fallback: string;
}

/**
 * Locked by Requirement 5.5: System Default first, followed by 17 Google
 * Fonts covering common sans, serif, display, and monospace needs.
 */
export const AVAILABLE_FONTS: readonly PortalFontOption[] = [
  {
    family: "System Default",
    fallback:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  },
  { family: "Inter", fallback: "sans-serif" },
  { family: "Roboto", fallback: "sans-serif" },
  { family: "Open Sans", fallback: "sans-serif" },
  { family: "Lato", fallback: "sans-serif" },
  { family: "Montserrat", fallback: "sans-serif" },
  { family: "Poppins", fallback: "sans-serif" },
  { family: "Source Sans 3", fallback: "sans-serif" },
  { family: "Plus Jakarta Sans", fallback: "sans-serif" },
  { family: "DM Sans", fallback: "sans-serif" },
  { family: "Nunito", fallback: "sans-serif" },
  { family: "Work Sans", fallback: "sans-serif" },
  { family: "Raleway", fallback: "sans-serif" },
  { family: "Playfair Display", fallback: "serif" },
  { family: "Merriweather", fallback: "serif" },
  { family: "Libre Baskerville", fallback: "serif" },
  { family: "Space Grotesk", fallback: "sans-serif" },
  { family: "JetBrains Mono", fallback: "monospace" },
] as const;

/**
 * Sentinel used by `loadGoogleFont` to short-circuit (no network request for
 * the system stack).
 */
export const SYSTEM_DEFAULT_FONT_FAMILY = "System Default";
