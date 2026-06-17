import { createTheme, type Theme } from "@mui/material/styles";

import type { PortalAppearance } from "../types/appearance.types";

/**
 * Return a WCAG-ready text color (`#ffffff` or `#000000`) for the given
 * background color. Uses the W3C luminance formula on the sRGB channels,
 * which matches MUI's internal `getContrastText` heuristic closely
 * enough for our purposes without pulling in `@mui/system`'s color
 * utilities.
 *
 * Accepts `#RGB`, `#RRGGBB`, `#RGBA`, `#RRGGBBAA`, and `rgb()`/`rgba()`
 * strings. Unknown formats fall back to `#ffffff` so the button stays
 * visible, matching the previous hardcoded value.
 */
export function pickContrastingText(
  backgroundColor: string,
  lightText = "#ffffff",
  darkText = "#000000"
): string {
  const { r, g, b } = parseRgbChannels(backgroundColor) ?? { r: 0, g: 0, b: 0 };

  // sRGB relative luminance per WCAG 2.x.
  const toLinear = (channel: number) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const luminance = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);

  // The 0.179 crossover keeps contrast ≥ 4.5:1 against pure white/black
  // across the full sRGB gamut. Lower values pick light text on dark
  // backgrounds; higher values pick dark text on light backgrounds.
  return luminance > 0.179 ? darkText : lightText;
}

function parseRgbChannels(value: string): { r: number; g: number; b: number } | null {
  if (!value) return null;
  const trimmed = value.trim();

  if (trimmed.startsWith("#")) {
    const hex = trimmed.slice(1);
    if (hex.length === 3 || hex.length === 4) {
      const r = parseInt(hex.charAt(0) + hex.charAt(0), 16);
      const g = parseInt(hex.charAt(1) + hex.charAt(1), 16);
      const b = parseInt(hex.charAt(2) + hex.charAt(2), 16);
      return Number.isFinite(r) && Number.isFinite(g) && Number.isFinite(b) ? { r, g, b } : null;
    }
    if (hex.length === 6 || hex.length === 8) {
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      return Number.isFinite(r) && Number.isFinite(g) && Number.isFinite(b) ? { r, g, b } : null;
    }
    return null;
  }

  const rgbMatch = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(trimmed);
  if (rgbMatch) {
    return {
      r: Number(rgbMatch[1]),
      g: Number(rgbMatch[2]),
      b: Number(rgbMatch[3]),
    };
  }
  return null;
}

/**
 * Builds a MUI `Theme` deterministically from a `PortalAppearance` snapshot.
 *
 * The mapping is a pure function of the input — the same `appearance` always
 * produces an equivalent theme (see Property 3: Theme determinism in
 * requirements 21.3/21.13).
 *
 * Fields driven by `appearance`:
 *   - Palette: mode, primary, background (default/paper), text (primary/secondary),
 *     divider, and a non-standard `accent` slot. The existing app-wide module
 *     augmentation in `src/theme/theme.ts` already declares `palette.accent`,
 *     so tests can read it directly.
 *   - Typography: quoted body family with a `system-ui` fallback; `h1..h6`
 *     quoted heading family with a `sans-serif` fallback and `headingFontWeight`.
 *   - Shape: `borderRadius = cardBorderRadius`.
 *   - Components:
 *       MuiPaper root: matching border radius and a conditional 1px border.
 *       MuiButton root: `textTransform: "none"`, `borderRadius: cardBorderRadius / 2`.
 *       MuiButton contained: `backgroundColor = primary`.
 */
export function createPortalTheme(appearance: PortalAppearance): Theme {
  const { mode, colors, typography, layout } = appearance;

  const bodyFontFamily = `"${typography.bodyFontFamily}", system-ui`;
  const headingFontFamily = `"${typography.headingFontFamily}", sans-serif`;

  const headingVariant = {
    fontFamily: headingFontFamily,
    fontWeight: typography.headingFontWeight,
  };

  return createTheme({
    palette: {
      mode,
      primary: { main: colors.primary },
      background: {
        default: colors.background,
        paper: colors.cardBackground,
      },
      text: {
        primary: colors.textPrimary,
        secondary: colors.textSecondary,
      },
      divider: colors.border,
      accent: { main: colors.accent },
    },
    typography: {
      fontFamily: bodyFontFamily,
      fontSize: typography.baseFontSize,
      h1: headingVariant,
      h2: headingVariant,
      h3: headingVariant,
      h4: headingVariant,
      h5: headingVariant,
      h6: headingVariant,
    },
    shape: {
      borderRadius: layout.cardBorderRadius,
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          // Force the scoped baseline to use the portal theme's text color
          // so all children (Typography, TextField labels, etc.) inherit it
          // instead of leaking the outer app theme's color.
          root: {
            color: colors.textPrimary,
            backgroundColor: colors.background,
          },
        },
      },
      MuiScopedCssBaseline: {
        styleOverrides: {
          root: {
            color: colors.textPrimary,
            backgroundColor: "transparent",
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: layout.cardBorderRadius,
            border: layout.cardBorder ? `1px solid ${colors.border}` : "none",
            backgroundColor: colors.cardBackground,
            color: colors.textPrimary,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
            borderRadius: layout.cardBorderRadius / 2,
          },
          contained: {
            backgroundColor: colors.primary,
            // Pick a contrasting text color so light primaries meet WCAG
            // contrast ratios instead of washing out white-on-pastel.
            color: pickContrastingText(colors.primary),
            "&:hover": {
              backgroundColor: colors.primary,
              opacity: 0.9,
            },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            color: colors.textPrimary,
            "& .MuiOutlinedInput-notchedOutline": {
              borderColor: colors.border,
            },
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: colors.textSecondary,
            },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
              borderColor: colors.primary,
            },
            "&.Mui-disabled": {
              color: colors.textSecondary,
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: colors.border,
              },
            },
          },
          input: {
            color: colors.textPrimary,
            "&.Mui-disabled": {
              WebkitTextFillColor: colors.textSecondary,
              color: colors.textSecondary,
            },
          },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: {
            color: colors.textSecondary,
            "&.Mui-focused": {
              color: colors.primary,
            },
            "&.Mui-disabled": {
              color: colors.textSecondary,
            },
          },
        },
      },
      MuiInputBase: {
        styleOverrides: {
          root: {
            color: colors.textPrimary,
          },
          input: {
            color: colors.textPrimary,
            "&::placeholder": {
              color: colors.textSecondary,
              opacity: 0.7,
            },
          },
        },
      },
      MuiTypography: {
        styleOverrides: {
          root: {
            color: "inherit",
          },
        },
      },
    },
  });
}
