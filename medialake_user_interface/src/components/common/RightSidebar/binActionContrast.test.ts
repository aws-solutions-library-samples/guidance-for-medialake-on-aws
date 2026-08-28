import { describe, it, expect } from "vitest";
import { createUnifiedTheme } from "@/theme/theme";
import { alpha } from "@mui/material/styles";
import { accentColor, type AccentRole } from "@/theme/accessibleAccent";

/**
 * WCAG contrast guard for palette accents drawn on `background.paper`.
 *
 * The theme's `.main` shades are tuned for light surfaces. On the dark paper they
 * measure primary 2.68:1, secondary 3.23:1 and error 3.55:1 — all below the 4.5:1
 * AA threshold for text, which is what made the dark-mode selection-bin buttons
 * read as blue on blue. These tests compute the ratios from the real theme so a
 * future palette edit cannot quietly reintroduce it.
 *
 * Covers the selection bin's action buttons and the workflow picker's selected
 * row, both of which route their accent through `accentColor`.
 */
type ActionPalette = AccentRole;

/** Parse any CSS colour MUI emits here (hex or rgb/rgba). */
const toRgb = (color: string): [number, number, number] => {
  const rgbMatch = color.match(/rgba?\(([^)]+)\)/);
  if (rgbMatch) {
    const parts = rgbMatch[1].split(",").map((p) => parseFloat(p.trim()));
    return [parts[0], parts[1], parts[2]];
  }
  const hex = color.replace("#", "");
  const full =
    hex.length === 3
      ? hex
          .split("")
          .map((c) => c + c)
          .join("")
      : hex;
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ];
};

/** Alpha component of an rgba() string, or 1 when opaque. */
const alphaOf = (color: string): number => {
  const m = color.match(/rgba\(([^)]+)\)/);
  if (!m) return 1;
  const parts = m[1].split(",").map((p) => parseFloat(p.trim()));
  return parts.length > 3 ? parts[3] : 1;
};

const relativeLuminance = (rgb: [number, number, number]): number => {
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const contrast = (fg: string, bg: string): number => {
  const a = relativeLuminance(toRgb(fg));
  const b = relativeLuminance(toRgb(bg));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
};

/** Composite a translucent colour over an opaque backdrop. */
const over = (translucent: string, backdrop: string): string => {
  const f = toRgb(translucent);
  const b = toRgb(backdrop);
  const a = alphaOf(translucent);
  const mix = f.map((c, i) => Math.round(c * a + b[i] * (1 - a)));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
};

const AA_TEXT = 4.5; // WCAG 2.1 SC 1.4.3, normal-size text
const UI_COMPONENT = 3; // WCAG 2.1 SC 1.4.11, non-text boundaries

const ROLES: ActionPalette[] = ["primary", "secondary", "error"];
const MODES: Array<"light" | "dark"> = ["light", "dark"];

/** Mirrors the component: bgcolor alpha(c, 0.04), hover alpha(c, 0.10). */
const REST_TINT = 0.04;
const HOVER_TINT = 0.1;

describe("selection-bin action colour contrast", () => {
  for (const mode of MODES) {
    const theme = createUnifiedTheme(mode);
    const paper = theme.palette.background.paper;

    describe(`${mode} mode`, () => {
      for (const role of ROLES) {
        const c = accentColor(theme, role);

        it(`${role} label clears AA at rest`, () => {
          const surface = over(alpha(c, REST_TINT), paper);
          expect(contrast(c, surface)).toBeGreaterThanOrEqual(AA_TEXT);
        });

        it(`${role} label clears AA while hovered`, () => {
          // The hover tint lightens the surface in dark mode, which is where the
          // naive `.light` shade fell to 4.28:1.
          const surface = over(alpha(c, HOVER_TINT), paper);
          expect(contrast(c, surface)).toBeGreaterThanOrEqual(AA_TEXT);
        });

        it(`${role} border clears the non-text UI threshold`, () => {
          const surface = over(alpha(c, REST_TINT), paper);
          const border = over(alpha(c, mode === "dark" ? 0.7 : 0.8), surface);
          expect(contrast(border, surface)).toBeGreaterThanOrEqual(UI_COMPONENT);
        });
      }
    });
  }

  it("regression: the raw .main shades would fail in dark mode", () => {
    // Documents the bug this guard exists for. If the palette is ever retuned so
    // that .main becomes readable on dark, this test should be revisited rather
    // than deleted.
    const dark = createUnifiedTheme("dark");
    const paper = dark.palette.background.paper;
    for (const role of ROLES) {
      const raw = dark.palette[role].main;
      const surface = over(alpha(raw, REST_TINT), paper);
      expect(contrast(raw, surface)).toBeLessThan(AA_TEXT);
    }
  });

  it("light mode keeps the primary shade that was already passing", () => {
    // The light palette was reported as good, so primary must not drift.
    const light = createUnifiedTheme("light");
    expect(accentColor(light, "primary")).toBe(light.palette.primary.main);
  });

  it("dark mode never falls back to a .main shade", () => {
    const dark = createUnifiedTheme("dark");
    for (const role of ROLES) {
      expect(accentColor(dark, role)).not.toBe(dark.palette[role].main);
    }
  });
});
