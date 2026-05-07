import React, { useCallback } from "react";
import {
  Box,
  FormControlLabel,
  MenuItem,
  Slider,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";

import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";
import type { PortalAppearanceLayout } from "../../../types/appearance.types";

/**
 * Options for the card-shadow dropdown. Values mirror the enum in
 * `PortalAppearanceLayout.cardShadow` (Requirement 6.3).
 */
const SHADOW_OPTIONS: ReadonlyArray<{
  value: PortalAppearanceLayout["cardShadow"];
  label: string;
}> = [
  { value: "none", label: "None" },
  { value: "sm", label: "Small" },
  { value: "md", label: "Medium" },
  { value: "lg", label: "Large" },
];

/**
 * LayoutSection
 *
 * Edits `appearance.layout`. Rendered inside the sidebar's "Layout"
 * accordion.
 *
 * Controls (top-to-bottom):
 *   1. Card max-width slider (400-1200, step 10) — Requirement 6.1.
 *   2. Card border-radius slider (0-32, step 1) — Requirement 6.2.
 *   3. Card shadow `TextField select` (none/sm/md/lg) — Requirement 6.3.
 *   4. Card padding slider (16-64, step 2) — Requirement 6.4.
 *   5. Card border `Switch` (boolean) — Requirement 6.5.
 *   6. Page vertical padding slider (0-120, step 4) — Requirement 6.6.
 *
 * Each slider label row shows a live pixel-value readout so users see
 * the numeric value while dragging.
 */
const LayoutSection: React.FC = () => {
  const layout = usePortalEditorStore((s) => s.appearance.layout);
  const updateLayout = usePortalEditorStore((s) => s.updateLayout);

  /**
   * Factory building a numeric slider onChange handler for a specific
   * layout key. Kept as a closure over `updateLayout` so the returned
   * handlers are simple and recreated only when the store setter
   * reference changes (Zustand setters are stable).
   */
  const makeNumericSliderHandler = useCallback(
    (
      key: Extract<
        keyof PortalAppearanceLayout,
        "cardMaxWidth" | "cardBorderRadius" | "cardPadding" | "pageVerticalPadding"
      >
    ) =>
      (_event: Event, value: number | number[]) => {
        if (typeof value !== "number") {
          return;
        }
        updateLayout({ [key]: value } as Partial<PortalAppearanceLayout>);
      },
    [updateLayout]
  );

  const handleShadowChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const next = event.target.value as PortalAppearanceLayout["cardShadow"];
      updateLayout({ cardShadow: next });
    },
    [updateLayout]
  );

  const handleCardBorderChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      updateLayout({ cardBorder: checked });
    },
    [updateLayout]
  );

  return (
    <Stack spacing={2}>
      {/* Card max-width */}
      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Card max-width
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {layout.cardMaxWidth}px
          </Typography>
        </Stack>
        <Slider
          value={layout.cardMaxWidth}
          onChange={makeNumericSliderHandler("cardMaxWidth")}
          min={400}
          max={1200}
          step={10}
          size="small"
          aria-label="Card max-width"
          valueLabelDisplay="auto"
        />
      </Box>

      {/* Card border radius */}
      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Border radius
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {layout.cardBorderRadius}px
          </Typography>
        </Stack>
        <Slider
          value={layout.cardBorderRadius}
          onChange={makeNumericSliderHandler("cardBorderRadius")}
          min={0}
          max={32}
          step={1}
          size="small"
          aria-label="Card border radius"
          valueLabelDisplay="auto"
        />
      </Box>

      {/* Card shadow */}
      <TextField
        select
        label="Card shadow"
        value={layout.cardShadow}
        onChange={handleShadowChange}
        size="small"
        fullWidth
      >
        {SHADOW_OPTIONS.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>

      {/* Card padding */}
      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Card padding
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {layout.cardPadding}px
          </Typography>
        </Stack>
        <Slider
          value={layout.cardPadding}
          onChange={makeNumericSliderHandler("cardPadding")}
          min={16}
          max={64}
          step={2}
          size="small"
          aria-label="Card padding"
          valueLabelDisplay="auto"
        />
      </Box>

      {/* Card border toggle */}
      <FormControlLabel
        control={
          <Switch checked={layout.cardBorder} onChange={handleCardBorderChange} size="small" />
        }
        label="Card border"
      />

      {/* Page vertical padding */}
      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Page vertical padding
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {layout.pageVerticalPadding}px
          </Typography>
        </Stack>
        <Slider
          value={layout.pageVerticalPadding}
          onChange={makeNumericSliderHandler("pageVerticalPadding")}
          min={0}
          max={120}
          step={4}
          size="small"
          aria-label="Page vertical padding"
          valueLabelDisplay="auto"
        />
      </Box>
    </Stack>
  );
};

export { LayoutSection };
export default React.memo(LayoutSection);
