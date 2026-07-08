import type { PortalAppearance } from "../types/appearance.types";

/**
 * Baseline `PortalAppearance` that mirrors today's hard-coded public portal
 * styling (neutral blue primary on a light `#f0f4f8` page, white card,
 * 40px vertical padding matching the current MUI `py: 5`).
 *
 * Used in three places:
 *  1. Create mode — seed for the visual editor when a new portal is drafted.
 *  2. Deep-merge backfill — merged with legacy portals that have no
 *     `appearance` field so older data still renders predictably.
 *  3. Public page fallback — consumed by `UploadPortalPage` whenever
 *     `portalConfig.appearance` is `undefined`.
 */
export const DEFAULT_PORTAL_APPEARANCE: PortalAppearance = {
  mode: "light",
  colors: {
    primary: "#2B6CB0",
    background: "#f0f4f8",
    cardBackground: "#ffffff",
    textPrimary: "#1a202c",
    textSecondary: "#4a5568",
    border: "#cbd5e0",
    accent: "#2B6CB0",
  },
  typography: {
    headingFontFamily: "Inter",
    bodyFontFamily: "Inter",
    baseFontSize: 16,
    headingFontWeight: 600,
  },
  layout: {
    cardMaxWidth: 680,
    cardBorderRadius: 12,
    cardShadow: "md",
    cardPadding: 32,
    cardBorder: false,
    pageVerticalPadding: 40,
  },
  branding: {
    showLogo: true,
    logoSize: 48,
    logoAlignment: "left",
    showPoweredBy: true,
    bannerHeight: 0,
  },
  content: {
    titleHtml: "",
    descriptionHtml: "",
    // Label for the uploader's OWN upload-trigger button (NOT the page-level
    // Submit/Complete action, which is a fixed i18n string — see
    // `UploadPortalPage.tsx`'s `model.completeText`). Defaulting this to
    // "Upload assets" keeps the two buttons visually and semantically
    // distinct out of the box; a value of "Submit" here would make the
    // upload-trigger button read the same as the authoritative Submit
    // button on any portal that collects a form submission.
    submitButtonText: "Upload assets",
    footerHtml: "",
    successMessage: "Upload complete! Thank you.",
    dropZoneText: "Drop files here or click to browse",
    buttonStyle: "contained",
    buttonRounding: "rounded",
  },
};

/**
 * Dark-mode counterpart of the default color palette. Applied automatically
 * when the admin toggles mode to "dark" via `AppearanceSection`. The primary
 * and accent colors are kept identical to the light defaults so the brand
 * identity is preserved; only the surface/text/border colors flip to
 * dark-appropriate values.
 */
export const DEFAULT_DARK_COLORS: PortalAppearance["colors"] = {
  primary: "#63B3ED",
  background: "#1a202c",
  cardBackground: "#2d3748",
  textPrimary: "#e2e8f0",
  textSecondary: "#a0aec0",
  border: "#4a5568",
  accent: "#63B3ED",
};

/**
 * Light-mode default colors — extracted from `DEFAULT_PORTAL_APPEARANCE`
 * for use by the mode-toggle handler so it can swap back cleanly.
 */
export const DEFAULT_LIGHT_COLORS: PortalAppearance["colors"] = DEFAULT_PORTAL_APPEARANCE.colors;
