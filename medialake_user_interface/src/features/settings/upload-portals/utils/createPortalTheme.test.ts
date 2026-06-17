import { describe, expect, it } from "vitest";

import { DEFAULT_PORTAL_APPEARANCE } from "../constants/appearanceDefaults";
import type { PortalAppearance } from "../types/appearance.types";
import { createPortalTheme } from "./createPortalTheme";

/**
 * Reads MUI component style overrides off a constructed theme. MUI types
 * declare `styleOverrides.{slot}` as `object | ((args) => object)`, so we cast
 * to a record to read the literal values our factory writes.
 */
function getComponentOverrides(
  theme: ReturnType<typeof createPortalTheme>,
  component: "MuiPaper" | "MuiButton"
): Record<string, Record<string, unknown>> {
  const components = theme.components as unknown as Record<
    string,
    { styleOverrides?: Record<string, Record<string, unknown>> }
  >;
  const overrides = components[component]?.styleOverrides;
  if (!overrides) {
    throw new Error(`Missing ${component} styleOverrides on theme`);
  }
  return overrides;
}

function buildAppearance(overrides: Partial<PortalAppearance>): PortalAppearance {
  return {
    ...DEFAULT_PORTAL_APPEARANCE,
    ...overrides,
    colors: { ...DEFAULT_PORTAL_APPEARANCE.colors, ...(overrides.colors ?? {}) },
    typography: {
      ...DEFAULT_PORTAL_APPEARANCE.typography,
      ...(overrides.typography ?? {}),
    },
    layout: { ...DEFAULT_PORTAL_APPEARANCE.layout, ...(overrides.layout ?? {}) },
    branding: {
      ...DEFAULT_PORTAL_APPEARANCE.branding,
      ...(overrides.branding ?? {}),
    },
    content: {
      ...DEFAULT_PORTAL_APPEARANCE.content,
      ...(overrides.content ?? {}),
    },
  };
}

describe("createPortalTheme", () => {
  describe("palette", () => {
    it("maps every color slot from appearance.colors to the palette", () => {
      const appearance = buildAppearance({
        colors: {
          primary: "#123456",
          background: "#abcdef",
          cardBackground: "#fafafa",
          textPrimary: "#111111",
          textSecondary: "#555555",
          border: "#dddddd",
          accent: "#ff00aa",
        },
      });

      const theme = createPortalTheme(appearance);

      expect(theme.palette.primary.main).toBe("#123456");
      expect(theme.palette.background.default).toBe("#abcdef");
      expect(theme.palette.background.paper).toBe("#fafafa");
      expect(theme.palette.text.primary).toBe("#111111");
      expect(theme.palette.text.secondary).toBe("#555555");
      expect(theme.palette.divider).toBe("#dddddd");
      expect(theme.palette.accent.main).toBe("#ff00aa");
    });

    it("uses palette.mode = 'dark' when appearance.mode === 'dark'", () => {
      const theme = createPortalTheme(buildAppearance({ mode: "dark" }));
      expect(theme.palette.mode).toBe("dark");
    });

    it("uses palette.mode = 'light' when appearance.mode === 'light'", () => {
      const theme = createPortalTheme(buildAppearance({ mode: "light" }));
      expect(theme.palette.mode).toBe("light");
    });
  });

  describe("typography", () => {
    it("wraps bodyFontFamily in double quotes and appends ', system-ui'", () => {
      const theme = createPortalTheme(
        buildAppearance({
          typography: {
            ...DEFAULT_PORTAL_APPEARANCE.typography,
            bodyFontFamily: "Roboto",
          },
        })
      );

      expect(theme.typography.fontFamily).toBe('"Roboto", system-ui');
    });

    it("sets typography.fontSize to appearance.typography.baseFontSize", () => {
      const theme = createPortalTheme(
        buildAppearance({
          typography: {
            ...DEFAULT_PORTAL_APPEARANCE.typography,
            baseFontSize: 18,
          },
        })
      );

      expect(theme.typography.fontSize).toBe(18);
    });

    it.each(["h1", "h2", "h3"] as const)(
      "applies quoted heading family + ', sans-serif' and configured weight to %s",
      (variant) => {
        const theme = createPortalTheme(
          buildAppearance({
            typography: {
              ...DEFAULT_PORTAL_APPEARANCE.typography,
              headingFontFamily: "Playfair Display",
              headingFontWeight: 800,
            },
          })
        );

        expect(theme.typography[variant].fontFamily).toBe('"Playfair Display", sans-serif');
        expect(theme.typography[variant].fontWeight).toBe(800);
      }
    );
  });

  describe("shape", () => {
    it("maps shape.borderRadius from appearance.layout.cardBorderRadius", () => {
      const theme = createPortalTheme(
        buildAppearance({
          layout: { ...DEFAULT_PORTAL_APPEARANCE.layout, cardBorderRadius: 20 },
        })
      );

      expect(theme.shape.borderRadius).toBe(20);
    });
  });

  describe("MuiPaper overrides", () => {
    it("uses cardBorderRadius and a 1px solid border when cardBorder === true", () => {
      const theme = createPortalTheme(
        buildAppearance({
          colors: {
            ...DEFAULT_PORTAL_APPEARANCE.colors,
            border: "#cccccc",
          },
          layout: {
            ...DEFAULT_PORTAL_APPEARANCE.layout,
            cardBorderRadius: 24,
            cardBorder: true,
          },
        })
      );

      const root = getComponentOverrides(theme, "MuiPaper").root;
      expect(root.borderRadius).toBe(24);
      expect(root.border).toBe("1px solid #cccccc");
    });

    it("sets border to 'none' when cardBorder === false", () => {
      const theme = createPortalTheme(
        buildAppearance({
          layout: {
            ...DEFAULT_PORTAL_APPEARANCE.layout,
            cardBorder: false,
          },
        })
      );

      const root = getComponentOverrides(theme, "MuiPaper").root;
      expect(root.border).toBe("none");
    });
  });

  describe("MuiButton overrides", () => {
    it("sets root.textTransform to 'none' and root.borderRadius to cardBorderRadius / 2", () => {
      const theme = createPortalTheme(
        buildAppearance({
          layout: {
            ...DEFAULT_PORTAL_APPEARANCE.layout,
            cardBorderRadius: 16,
          },
        })
      );

      const overrides = getComponentOverrides(theme, "MuiButton");
      expect(overrides.root.textTransform).toBe("none");
      expect(overrides.root.borderRadius).toBe(8);
    });

    it("sets contained.backgroundColor to the primary color", () => {
      const theme = createPortalTheme(
        buildAppearance({
          colors: {
            ...DEFAULT_PORTAL_APPEARANCE.colors,
            primary: "#0055aa",
          },
        })
      );

      const overrides = getComponentOverrides(theme, "MuiButton");
      expect(overrides.contained.backgroundColor).toBe("#0055aa");
    });
  });
});
