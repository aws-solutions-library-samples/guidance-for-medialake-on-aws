/**
 * Portal Appearance Runtime Validation Schema
 *
 * This file is the runtime validation surface for the `PortalAppearance`
 * configuration. Every `PortalAppearance` value that crosses a trust boundary
 * (API request / response, persisted localStorage draft, user-visible editor
 * save path) must pass `portalAppearanceSchema.safeParse(...)` before it is
 * treated as a trusted, typed `PortalAppearance`.
 *
 * The schema intentionally mirrors — field for field, constraint for
 * constraint — the TypeScript interfaces in
 * `../types/appearance.types.ts`. The two must stay in lockstep. See the
 * JSDoc on `PortalAppearance` in that file for the rationale; the
 * `_schemaMatchesInterface` assertion at the bottom of this file is the
 * compile-time guard that enforces that lockstep.
 *
 * Sub-schemas are exported individually so slices of the editor (for
 * example the `colors` sidebar section) can validate just the portion of
 * state they own without re-parsing the whole appearance object.
 */

import { z } from "zod";

import type {
  PortalAppearance,
  PortalAppearanceBranding,
  PortalAppearanceColors,
  PortalAppearanceContent,
  PortalAppearanceLayout,
  PortalAppearanceTypography,
} from "../types/appearance.types";

/**
 * Matches `#RGB`, `#RGBA`, `#RRGGBB`, or `#RRGGBBAA`. Case-insensitive
 * on hex digits. Invalid lengths (4-digit without alpha, 5, 7) are
 * explicitly rejected so ``#12345`` can't slip past validation.
 */
export const HEX_COLOR_RE = /^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/;

/**
 * Matches `rgb(r, g, b)` and `rgba(r, g, b, a)` with an optional alpha in
 * `[0, 1]` (either `0`, `1`, or a fractional value like `0.5` / `.5`).
 * Whitespace around separators is allowed; channel values are not bounded
 * here because the hex branch is already the canonical form the editor
 * emits — the regex simply keeps obviously malformed inputs out.
 */
export const RGBA_COLOR_RE = /^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(,\s*(0|1|0?\.\d+)\s*)?\)$/;

const COLOR_ERROR_MESSAGE = "Must be a hex color like #RRGGBB or rgba(r,g,b,a)";

/**
 * Reusable union schema for every color-valued field in `appearance.colors`.
 * Exported so downstream callers (e.g. the `ColorPicker` hex input) can
 * validate a single color string without instantiating a parent object.
 */
export const colorStringSchema = z
  .string()
  .refine((value) => HEX_COLOR_RE.test(value) || RGBA_COLOR_RE.test(value), {
    message: COLOR_ERROR_MESSAGE,
  });

/** Seven-color palette. Mirrors `PortalAppearanceColors`. */
export const colorsSchema = z.object({
  primary: colorStringSchema,
  background: colorStringSchema,
  cardBackground: colorStringSchema,
  textPrimary: colorStringSchema,
  textSecondary: colorStringSchema,
  border: colorStringSchema,
  accent: colorStringSchema,
});

/** Typography block. Mirrors `PortalAppearanceTypography`. */
export const typographySchema = z.object({
  headingFontFamily: z.string().min(1),
  bodyFontFamily: z.string().min(1),
  baseFontSize: z.number().int().min(12).max(24),
  headingFontWeight: z.number().int().min(100).max(900),
});

/** Layout block. Mirrors `PortalAppearanceLayout`. */
export const layoutSchema = z.object({
  cardMaxWidth: z.number().int().min(400).max(1200),
  cardBorderRadius: z.number().int().min(0).max(32),
  cardShadow: z.enum(["none", "sm", "md", "lg"]),
  cardPadding: z.number().int().min(16).max(64),
  cardBorder: z.boolean(),
  pageVerticalPadding: z.number().int().min(0).max(120),
});

/** Branding block. Mirrors `PortalAppearanceBranding`. */
export const brandingSchema = z.object({
  // `.default(true)` keeps legacy appearance payloads (saved before the
  // show-logo toggle existed) valid: they parse to `showLogo: true`, matching
  // the prior always-show behavior.
  showLogo: z.boolean().default(true),
  logoSize: z.number().int().min(24).max(120),
  logoAlignment: z.enum(["left", "center"]),
  showPoweredBy: z.boolean(),
  bannerS3Key: z.string().optional(),
  bannerUrl: z.string().optional(),
  bannerHeight: z.number().int().min(0).max(400),
  faviconS3Key: z.string().optional(),
  faviconUrl: z.string().optional(),
});

/** Rich-text content block. Mirrors `PortalAppearanceContent`. */
export const contentSchema = z.object({
  titleHtml: z.string().max(5000),
  descriptionHtml: z.string().max(10000),
  submitButtonText: z.string().min(1).max(50),
  footerHtml: z.string().max(2000),
  successMessage: z.string().max(500),
  dropZoneText: z.string().max(200),
  buttonStyle: z.enum(["contained", "outlined", "text"]),
  buttonRounding: z.enum(["square", "rounded", "pill"]),
});

/**
 * Top-level schema for the full `PortalAppearance` object. Compose the five
 * slice schemas above to keep the definition DRY.
 */
export const portalAppearanceSchema = z.object({
  mode: z.enum(["light", "dark"]),
  colors: colorsSchema,
  typography: typographySchema,
  layout: layoutSchema,
  branding: brandingSchema,
  content: contentSchema,
});

/**
 * Type inferred from the runtime schema. Kept as an export so downstream
 * code can refer to the "schema-side" type where useful (for example when
 * typing `z.infer` results of `safeParse`).
 */
export type PortalAppearanceFromSchema = z.infer<typeof portalAppearanceSchema>;

/**
 * Compile-time lockstep assertion between the hand-written
 * `PortalAppearance` interface and the schema-inferred type. Either
 * direction of assignability would be sufficient to prove structural
 * equivalence for the shapes we care about, but doing both makes the
 * intent unambiguous and catches drift in either direction:
 *
 *   - If the interface grows a field the schema doesn't validate, the
 *     first assertion fails.
 *   - If the schema grows a field the interface doesn't model, the second
 *     assertion fails.
 *
 * These are erased at runtime (the `as` casts go through `unknown` to
 * keep strict `noUncheckedIndexedAccess`-style configs happy) and cost
 * nothing in the shipped bundle.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _schemaMatchesInterface: PortalAppearance = {} as PortalAppearanceFromSchema;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _interfaceMatchesSchema: PortalAppearanceFromSchema = {} as PortalAppearance;

// Re-export the slice-level shape types inferred from the schemas so
// callers that prefer the schema-derived types can opt in. The hand-written
// interfaces remain the primary public surface.
export type PortalAppearanceColorsFromSchema = z.infer<typeof colorsSchema>;
export type PortalAppearanceTypographyFromSchema = z.infer<typeof typographySchema>;
export type PortalAppearanceLayoutFromSchema = z.infer<typeof layoutSchema>;
export type PortalAppearanceBrandingFromSchema = z.infer<typeof brandingSchema>;
export type PortalAppearanceContentFromSchema = z.infer<typeof contentSchema>;

// Prevent "unused import" warnings for the interface-side slice types
// while still making them available to downstream consumers through the
// public `types/appearance.types` module. Assigning each to a void-typed
// local keeps lint rules happy without emitting runtime code.
type _UnusedSliceTypes =
  | PortalAppearanceColors
  | PortalAppearanceTypography
  | PortalAppearanceLayout
  | PortalAppearanceBranding
  | PortalAppearanceContent;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _slicesReferenced: _UnusedSliceTypes | undefined = undefined;
