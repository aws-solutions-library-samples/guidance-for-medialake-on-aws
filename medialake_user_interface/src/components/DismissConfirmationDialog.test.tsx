import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "@mui/material/styles";
import { createUnifiedTheme } from "@/theme/theme";
import { DismissConfirmationDialog } from "./DismissConfirmationDialog";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => (key === "notifications.label" ? "Notification" : key),
  }),
}));

type RGBA = [number, number, number, number];

function parseColor(value: string): RGBA {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const rgb = value.match(/rgba?\(([^)]+)\)/);
  if (!rgb) throw new Error(`Unparseable color: ${value}`);
  const [r, g, b, a = "1"] = rgb[1].split(",").map((s) => s.trim());
  return [Number(r), Number(g), Number(b), Number(a)];
}

/** Composite a translucent color over an opaque one. */
function over([r, g, b, a]: RGBA, [br, bg, bb]: RGBA): RGBA {
  return [r * a + br * (1 - a), g * a + bg * (1 - a), b * a + bb * (1 - a), 1];
}

function luminance([r, g, b]: RGBA): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: RGBA, b: RGBA): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function renderIn(mode: "light" | "dark") {
  const theme = createUnifiedTheme(mode);
  render(
    <ThemeProvider theme={theme}>
      <DismissConfirmationDialog
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        notificationMessage="Zip download: 3 zipped files"
      />
    </ThemeProvider>
  );
  const summary = screen.getByTestId("dismiss-notification-summary");
  const paper = parseColor(theme.palette.background.paper);
  const background = over(parseColor(getComputedStyle(summary).backgroundColor), paper);
  return { theme, summary, background };
}

describe("DismissConfirmationDialog notification summary", () => {
  it.each(["light", "dark"] as const)("is readable in %s mode", (mode) => {
    const { theme, summary, background } = renderIn(mode);

    expect(summary).toHaveTextContent("Notification: Zip download: 3 zipped files");
    // WCAG AA for normal text. In dark mode the old fixed light-grey box put
    // near-white text on a near-white background (contrast ~1.1).
    for (const color of [theme.palette.text.primary, theme.palette.text.secondary]) {
      const text = over(parseColor(color), background);
      expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("follows the dialog surface in dark mode instead of a light grey", () => {
    const { background } = renderIn("dark");
    // Dark surface: well below mid-grey luminance.
    expect(luminance(background)).toBeLessThan(0.1);
  });
});
