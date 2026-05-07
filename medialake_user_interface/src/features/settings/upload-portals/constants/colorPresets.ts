/**
 * Preset color schemes for the portal visual editor Appearance section.
 *
 * Selecting a preset swaps all seven colors in
 * `appearance.colors` via `updateAppearance({ colors: preset.colors })`.
 * The four presets below are the minimum required by Requirement 4.3;
 * additional presets can be appended without touching consumer code.
 */

import type { PortalAppearanceColors } from "../types/appearance.types";

export interface PortalColorPreset {
  /** Stable identifier used as a React key and for analytics. */
  id: "ocean" | "forest" | "sunset" | "monochrome";
  /** Display label shown in the Appearance section preset row. */
  label: string;
  /** The full seven-color palette applied when the preset is selected. */
  colors: PortalAppearanceColors;
}

export const COLOR_PRESETS: readonly PortalColorPreset[] = [
  {
    id: "ocean",
    label: "Ocean",
    colors: {
      primary: "#0077B6",
      background: "#F0F9FF",
      cardBackground: "#FFFFFF",
      textPrimary: "#0B1F33",
      textSecondary: "#3C5A72",
      border: "#CFE3F1",
      accent: "#00B4D8",
    },
  },
  {
    id: "forest",
    label: "Forest",
    colors: {
      primary: "#2D6A4F",
      background: "#F2F7F2",
      cardBackground: "#FFFFFF",
      textPrimary: "#0F1F17",
      textSecondary: "#3D5A4A",
      border: "#D4E2D8",
      accent: "#95D5B2",
    },
  },
  {
    id: "sunset",
    label: "Sunset",
    colors: {
      primary: "#E63946",
      background: "#FFF5F0",
      cardBackground: "#FFFFFF",
      textPrimary: "#2B0F0F",
      textSecondary: "#7A4840",
      border: "#F5D6CA",
      accent: "#F4A261",
    },
  },
  {
    id: "monochrome",
    label: "Monochrome",
    colors: {
      primary: "#111827",
      background: "#F3F4F6",
      cardBackground: "#FFFFFF",
      textPrimary: "#111827",
      textSecondary: "#4B5563",
      border: "#E5E7EB",
      accent: "#374151",
    },
  },
] as const;
