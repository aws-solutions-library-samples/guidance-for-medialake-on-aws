import { describe, expect, it } from "vitest";
import fc from "fast-check";

import type { PortalAppearance } from "../types/appearance.types";
import { createPortalTheme } from "./createPortalTheme";

/**
 * Validates: Requirements 21.3, 21.13
 *
 * Property 3: Theme determinism.
 *
 *   ∀ a, b: PortalAppearance. deepEqual(a, b) ⟹ createPortalTheme(a) and
 *   createPortalTheme(b) produce equivalent themes.
 *
 * We feed the factory an appearance arbitrary and a `structuredClone` of it,
 * then compare a serializable projection over the theme surface that
 * `createPortalTheme` actually writes to — palette slots we set, typography
 * fields, shape.borderRadius, and both MuiPaper and MuiButton overrides.
 * Non-written bits of the MUI theme (e.g. `typography.body1`) are intentionally
 * excluded; this property is about the factory, not about MUI internals.
 */

const colorArb = fc.constantFrom(
  "#ff0000",
  "#00ff00",
  "#0000ff",
  "#2B6CB0",
  "#1a202c",
  "#f0f4f8",
  "#ffffff",
  "#e2e8f0"
);

const familyArb = fc.constantFrom("Inter", "Roboto", "System Default");

const appearanceArb: fc.Arbitrary<PortalAppearance> = fc.record({
  mode: fc.constantFrom("light", "dark") as fc.Arbitrary<"light" | "dark">,
  colors: fc.record({
    primary: colorArb,
    background: colorArb,
    cardBackground: colorArb,
    textPrimary: colorArb,
    textSecondary: colorArb,
    border: colorArb,
    accent: colorArb,
  }),
  typography: fc.record({
    headingFontFamily: familyArb,
    bodyFontFamily: familyArb,
    baseFontSize: fc.integer({ min: 12, max: 24 }),
    headingFontWeight: fc.constantFrom(400, 500, 600, 700, 800, 900),
  }),
  layout: fc.record({
    cardMaxWidth: fc.integer({ min: 400, max: 1200 }),
    cardBorderRadius: fc.integer({ min: 0, max: 32 }),
    cardShadow: fc.constantFrom("none", "sm", "md", "lg") as fc.Arbitrary<
      "none" | "sm" | "md" | "lg"
    >,
    cardPadding: fc.integer({ min: 16, max: 64 }),
    cardBorder: fc.boolean(),
    pageVerticalPadding: fc.integer({ min: 0, max: 120 }),
  }),
  branding: fc.record({
    logoSize: fc.integer({ min: 24, max: 120 }),
    logoAlignment: fc.constantFrom("left", "center") as fc.Arbitrary<"left" | "center">,
    showPoweredBy: fc.boolean(),
    bannerHeight: fc.integer({ min: 0, max: 400 }),
  }),
  content: fc.constant({
    titleHtml: "",
    descriptionHtml: "",
    submitButtonText: "Submit",
    footerHtml: "",
    successMessage: "Upload complete!",
    dropZoneText: "Drop files here",
    buttonStyle: "contained" as const,
    buttonRounding: "rounded" as const,
  }),
});

/**
 * Serializable projection over the surface `createPortalTheme` actually
 * writes. Two themes built from deep-equal inputs must have equal projections.
 */
function projectTheme(theme: ReturnType<typeof createPortalTheme>) {
  const components = theme.components as unknown as Record<
    string,
    { styleOverrides?: Record<string, Record<string, unknown>> }
  >;
  const paperOverrides = components.MuiPaper?.styleOverrides ?? {};
  const buttonOverrides = components.MuiButton?.styleOverrides ?? {};

  return {
    palette: {
      mode: theme.palette.mode,
      primary: { main: theme.palette.primary.main },
      background: {
        default: theme.palette.background.default,
        paper: theme.palette.background.paper,
      },
      text: {
        primary: theme.palette.text.primary,
        secondary: theme.palette.text.secondary,
      },
      divider: theme.palette.divider,
      accent: { main: theme.palette.accent.main },
    },
    typography: {
      fontFamily: theme.typography.fontFamily,
      fontSize: theme.typography.fontSize,
      h1: {
        fontFamily: theme.typography.h1.fontFamily,
        fontWeight: theme.typography.h1.fontWeight,
      },
      h2: {
        fontFamily: theme.typography.h2.fontFamily,
        fontWeight: theme.typography.h2.fontWeight,
      },
      h3: {
        fontFamily: theme.typography.h3.fontFamily,
        fontWeight: theme.typography.h3.fontWeight,
      },
      h4: {
        fontFamily: theme.typography.h4.fontFamily,
        fontWeight: theme.typography.h4.fontWeight,
      },
      h5: {
        fontFamily: theme.typography.h5.fontFamily,
        fontWeight: theme.typography.h5.fontWeight,
      },
      h6: {
        fontFamily: theme.typography.h6.fontFamily,
        fontWeight: theme.typography.h6.fontWeight,
      },
    },
    shape: { borderRadius: theme.shape.borderRadius },
    components: {
      MuiPaper: { root: paperOverrides.root ?? null },
      MuiButton: {
        root: buttonOverrides.root ?? null,
        contained: buttonOverrides.contained ?? null,
      },
    },
  };
}

describe("Feature: portal-visual-editor, Property 3: Theme determinism", () => {
  it("deepEqual inputs produce equivalent themes", () => {
    fc.assert(
      fc.property(appearanceArb, (a) => {
        const b = structuredClone(a);

        const themeA = createPortalTheme(a);
        const themeB = createPortalTheme(b);

        expect(projectTheme(themeA)).toEqual(projectTheme(themeB));
      }),
      { numRuns: 100 }
    );
  });
});
