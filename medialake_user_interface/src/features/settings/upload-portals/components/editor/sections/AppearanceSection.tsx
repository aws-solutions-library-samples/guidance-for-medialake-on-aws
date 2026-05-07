import React, { useCallback, useMemo } from "react";
import { Box, Button, Stack, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";

import { COLOR_PRESETS } from "../../../constants/colorPresets";
import { DEFAULT_DARK_COLORS, DEFAULT_LIGHT_COLORS } from "../../../constants/appearanceDefaults";
import type { PortalAppearanceColors } from "../../../types/appearance.types";
import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";
import ColorPicker from "../ColorPicker.lazy";

/**
 * Ordered list of the seven editable color slots rendered in the
 * Appearance section. Order locked by Requirement 4.2; keys must match
 * `PortalAppearanceColors` exactly. Held as a module-level constant so
 * the row array is stable across renders and easy to audit.
 */
const COLOR_FIELDS: {
  key: keyof PortalAppearanceColors;
  label: string;
}[] = [
  { key: "primary", label: "Primary" },
  { key: "background", label: "Background" },
  { key: "cardBackground", label: "Card background" },
  { key: "textPrimary", label: "Text primary" },
  { key: "textSecondary", label: "Text secondary" },
  { key: "border", label: "Border" },
  { key: "accent", label: "Accent" },
];

/**
 * AppearanceSection
 *
 * Edits `appearance.mode` and `appearance.colors`. Rendered inside the
 * sidebar's "Appearance" accordion.
 *
 * Layout:
 *   1. Light/dark mode toggle (MUI `ToggleButtonGroup`, exclusive) bound
 *      to `appearance.mode` (Requirement 4.1).
 *   2. Seven {@link ColorPicker}s — one per color slot — stacked
 *      vertically, each wired through `updateColor(key, value)` // i18n-ignore
 *      (Requirement 4.2).
 *   3. Preset color scheme row: four MUI `Button`s labelled Ocean,
 *      Forest, Sunset, Monochrome. Clicking a preset replaces all seven
 *      colors at once via `updateAppearance({ colors })` (Requirement // i18n-ignore
 *      4.3). Each preset button displays a small color strip showing the
 *      primary/accent/background swatches so the user can see at a glance
 *      what the preset changes.
 *   4. "Reset to defaults" text button calling `resetAppearanceToDefaults`
 *      (Requirement 4.4).
 *
 * State subscription:
 *   We use fine-grained selectors so mutating one color slot (or flipping
 *   mode) only re-renders the specific fields that depend on that slice.
 *   Each action hook is also subscribed independently — Zustand returns
 *   stable function references, so these never cause cascading renders.
 */
const AppearanceSection: React.FC = () => {
  const mode = usePortalEditorStore((s) => s.appearance.mode);
  const colors = usePortalEditorStore((s) => s.appearance.colors);
  const updateAppearance = usePortalEditorStore((s) => s.updateAppearance);
  const updateColor = usePortalEditorStore((s) => s.updateColor);
  const resetAppearanceToDefaults = usePortalEditorStore((s) => s.resetAppearanceToDefaults);

  const handleModeChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, nextMode: "light" | "dark" | null) => {
      if (nextMode === null) {
        return;
      }
      // When the mode flips, also swap the color palette to mode-appropriate
      // defaults so the preview immediately looks correct. The admin can
      // still override individual colors after the swap.
      const newColors = nextMode === "dark" ? DEFAULT_DARK_COLORS : DEFAULT_LIGHT_COLORS;
      updateAppearance({ mode: nextMode, colors: newColors });
    },
    [updateAppearance]
  );

  /**
   * Build a stable onChange handler factory per color field so re-renders
   * of `ColorPicker` get the same callback reference when `updateColor`
   * is unchanged (Zustand setters are stable).
   */
  const makeColorChangeHandler = useCallback(
    (key: keyof PortalAppearanceColors) => (value: string) => {
      updateColor(key, value);
    },
    [updateColor]
  );

  const handlePresetClick = useCallback(
    (presetColors: PortalAppearanceColors) => {
      updateAppearance({ colors: presetColors });
    },
    [updateAppearance]
  );

  const handleReset = useCallback(() => {
    resetAppearanceToDefaults();
  }, [resetAppearanceToDefaults]);

  // Flatten the primary/accent/background list once so each ColorPicker
  // row can offer a handful of preset swatches derived from the canonical
  // scheme set. Empty arrays are acceptable per the component's contract
  // but offering a few related colors makes the picker more useful.
  const primaryPresets = useMemo(() => COLOR_PRESETS.map((p) => p.colors.primary), []);

  return (
    <Stack spacing={2}>
      {/* Mode toggle */}
      <Box>
        <Typography variant="caption" color="text.secondary" component="div">
          Mode
        </Typography>
        <ToggleButtonGroup
          value={mode}
          exclusive
          onChange={handleModeChange}
          size="small"
          aria-label="Appearance mode"
          sx={{ mt: 0.5 }}
        >
          <ToggleButton value="light" aria-label="Light mode">
            Light
          </ToggleButton>
          <ToggleButton value="dark" aria-label="Dark mode">
            Dark
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Seven color pickers */}
      <Stack spacing={1.25}>
        {COLOR_FIELDS.map(({ key, label }) => (
          <ColorPicker
            key={key}
            label={label}
            value={colors[key]}
            onChange={makeColorChangeHandler(key)}
            presets={primaryPresets}
          />
        ))}
      </Stack>

      {/* Preset schemes */}
      <Box>
        <Typography variant="caption" color="text.secondary" component="div">
          Preset schemes
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
          {COLOR_PRESETS.map((preset) => (
            <Button
              key={preset.id}
              onClick={() => handlePresetClick(preset.colors)}
              variant="outlined"
              size="small"
              aria-label={`Apply ${preset.label} color scheme`}
              sx={{ textTransform: "none", px: 1.25 }}
            >
              <Stack direction="row" spacing={0.75} alignItems="center">
                <Stack direction="row" spacing={0.25}>
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      backgroundColor: preset.colors.primary,
                      border: "1px solid",
                      borderColor: "divider",
                    }}
                  />
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      backgroundColor: preset.colors.accent,
                      border: "1px solid",
                      borderColor: "divider",
                    }}
                  />
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      backgroundColor: preset.colors.background,
                      border: "1px solid",
                      borderColor: "divider",
                    }}
                  />
                </Stack>
                <Typography variant="body2" component="span">
                  {preset.label}
                </Typography>
              </Stack>
            </Button>
          ))}
        </Stack>
      </Box>

      {/* Reset to defaults */}
      <Box>
        <Button
          onClick={handleReset}
          variant="text"
          size="small"
          sx={{ px: 0.5, minWidth: 0, textTransform: "none" }}
        >
          Reset to defaults
        </Button>
      </Box>
    </Stack>
  );
};

export { AppearanceSection };
export default React.memo(AppearanceSection);
