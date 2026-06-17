/**
 * Portal Appearance Types
 *
 * This file is the single source of truth for the `PortalAppearance` type and
 * its sub-shapes (colors, typography, layout, branding, content). Every other
 * part of the portal visual editor — the Zustand store, `createPortalTheme`,
 * the live preview, the public `UploadPortalPage`, and the backend payload —
 * builds on these interfaces.
 *
 * The Zod validation schema (`portalAppearanceSchema`, added in task 2.8 at
 * `src/features/settings/upload-portals/schemas/appearance.schema.ts`) must
 * stay in lockstep with these interfaces: any change to a field name, type,
 * or documented numeric range here MUST be mirrored in the schema in the same
 * change, otherwise runtime validation will drift from the compile-time type.
 */

export interface PortalAppearance {
  mode: "light" | "dark";
  colors: PortalAppearanceColors;
  typography: PortalAppearanceTypography;
  layout: PortalAppearanceLayout;
  branding: PortalAppearanceBranding;
  content: PortalAppearanceContent;
}

export interface PortalAppearanceColors {
  primary: string; // hex or rgba
  background: string;
  cardBackground: string;
  textPrimary: string;
  textSecondary: string;
  border: string;
  accent: string;
}

export interface PortalAppearanceTypography {
  headingFontFamily: string; // Google Fonts name or system stack
  bodyFontFamily: string;
  baseFontSize: number; // 12–24 px
  headingFontWeight: number; // 100–900
}

export interface PortalAppearanceLayout {
  cardMaxWidth: number; // 400–1200 px
  cardBorderRadius: number; // 0–32 px
  cardShadow: "none" | "sm" | "md" | "lg";
  cardPadding: number; // 16–64 px
  cardBorder: boolean;
  pageVerticalPadding: number; // 0–120 px
}

export interface PortalAppearanceBranding {
  /** When false, the logo (and its fallback icon) is hidden entirely. */
  showLogo: boolean;
  logoSize: number; // 24–120 px
  logoAlignment: "left" | "center";
  showPoweredBy: boolean;
  bannerS3Key?: string;
  bannerUrl?: string; // resolved at read-time, not stored
  bannerHeight: number; // 0–400 px; 0 means no banner
  /** S3 key for a custom favicon. Resolved to a URL server-side. */
  faviconS3Key?: string;
  /** Resolved favicon URL (read-time only, not persisted by the client). */
  faviconUrl?: string;
}

export interface PortalAppearanceContent {
  titleHtml: string; // max 5000
  descriptionHtml: string; // max 10000
  submitButtonText: string; // 1–50
  footerHtml: string; // max 2000
  /** Message shown after a successful upload. Max 500 chars. */
  successMessage: string;
  /** Text shown in the upload drop zone. Max 200 chars. */
  dropZoneText: string;
  /** Visual style of the submit button. */
  buttonStyle: "contained" | "outlined" | "text";
  /** Border-radius style of the submit button. */
  buttonRounding: "square" | "rounded" | "pill";
}

/**
 * Allowed file types for a portal. Empty array means "accept all".
 * Each entry is a MIME pattern (e.g. "image/*", "video/*") or a file
 * extension with dot (e.g. ".pdf", ".docx").
 */
export type PortalAllowedFileTypes = string[];
