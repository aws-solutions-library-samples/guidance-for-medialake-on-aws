import { lighten, type Theme } from "@mui/material/styles";

/** Palette roles used as accents on `background.paper` surfaces. */
export type AccentRole = "primary" | "secondary" | "error";

/**
 * A palette accent that stays readable as text on `background.paper`, in both
 * theme modes.
 *
 * The palette's `.main` shades are tuned for light surfaces. Measured against the
 * dark paper (#1E2732) they fail the WCAG AA text threshold of 4.5:1:
 *
 *   primary   #2B6CB0  2.68:1
 *   secondary #6366F1  3.23:1
 *   error     #E53E3E  3.55:1
 *
 * That 2.68:1 is why blue-on-blue accents were hard to read in dark mode.
 *
 * Dark mode therefore uses the `.light` shade lifted further. `.light` alone
 * clears AA at rest (4.65:1) but slips to 4.28:1 once a hover tint lightens the
 * surface beneath it, so it is lightened until both states pass:
 *
 *   primary   #68ade7  5.88:1 rest / 5.27:1 hover
 *   secondary #9aa3f9  6.02:1 rest / 5.41:1 hover
 *   error     #fc8e8e  6.33:1 rest / 5.70:1 hover
 *
 * Light mode keeps `primary.main`: it already clears AA at 5.14:1 and is the
 * established look. `secondary.main` (4.26:1) and `error.main` (3.90:1) sit under
 * the threshold, so those take their `.dark` shade for 5.94:1 and 5.16:1.
 *
 * Use this anywhere a palette hue is drawn as text, an icon, or a focus ring on a
 * paper surface. It is not needed for text on a *filled* accent background —
 * there `contrastText` already handles it.
 *
 * Ratios are enforced by `binActionContrast.test.ts`, which computes them from
 * the real theme rather than trusting these numbers.
 */
export const accentColor = (theme: Theme, role: AccentRole): string => {
  const palette = theme.palette[role];
  if (theme.palette.mode === "dark") {
    // error.light is already bright enough that a 0.2 lift would wash it out.
    return lighten(palette.light, role === "error" ? 0.1 : 0.2);
  }
  return role === "primary" ? palette.main : palette.dark;
};
