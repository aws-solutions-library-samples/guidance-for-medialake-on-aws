import React, { useCallback } from "react";
import { Box, MenuItem, Slider, Stack, TextField, Typography } from "@mui/material";

import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";
import FontSelector from "../FontSelector";

/**
 * Heading-weight options rendered in the weight dropdown. Kept as a
 * module-level constant so the array reference is stable across renders.
 * Matches Requirement 5.3 (400, 500, 600, 700, 800, 900).
 */
const HEADING_WEIGHT_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 400, label: "400 — Regular" },
  { value: 500, label: "500 — Medium" },
  { value: 600, label: "600 — Semibold" },
  { value: 700, label: "700 — Bold" },
  { value: 800, label: "800 — Extrabold" },
  { value: 900, label: "900 — Black" },
];

/**
 * TypographySection
 *
 * Edits `appearance.typography`. Rendered inside the sidebar's
 * "Typography" accordion.
 *
 * Layout:
 *   1. Heading font `FontSelector` bound to `headingFontFamily`
 *      (Requirement 5.1).
 *   2. Body font `FontSelector` bound to `bodyFontFamily` (Requirement
 *      5.1).
 *   3. Base size slider (12-24, step 1) bound to `baseFontSize`
 *      (Requirement 5.2). Current value echoed next to the label so
 *      users can see the numeric value while dragging.
 *   4. Heading weight `TextField select` bound to `headingFontWeight`
 *      with options 400-900 step 100 (Requirement 5.3).
 *   5. `Aa` preview Typography element marked `aria-hidden="true"`
 *      (Requirements 5.4 and 16.15) using the current heading family,
 *      `baseFontSize * 2` for visual weight, and the current heading // i18n-ignore
 *      weight.
 *
 * State subscription:
 *   Fine-grained selectors keep typography-only edits from re-rendering
 *   unrelated sections.
 */
const TypographySection: React.FC = () => {
  const typography = usePortalEditorStore((s) => s.appearance.typography);
  const updateTypography = usePortalEditorStore((s) => s.updateTypography);

  const handleHeadingFontChange = useCallback(
    (family: string) => {
      updateTypography({ headingFontFamily: family });
    },
    [updateTypography]
  );

  const handleBodyFontChange = useCallback(
    (family: string) => {
      updateTypography({ bodyFontFamily: family });
    },
    [updateTypography]
  );

  const handleBaseSizeChange = useCallback(
    (_event: Event, value: number | number[]) => {
      // MUI `Slider` with a single thumb always yields a plain number;
      // the `number[]` branch is unreachable but must be narrowed.
      if (typeof value !== "number") {
        return;
      }
      updateTypography({ baseFontSize: value });
    },
    [updateTypography]
  );

  const handleHeadingWeightChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const next = Number(event.target.value);
      if (Number.isFinite(next)) {
        updateTypography({ headingFontWeight: next });
      }
    },
    [updateTypography]
  );

  return (
    <Stack spacing={2}>
      <FontSelector
        label="Heading font"
        value={typography.headingFontFamily}
        onChange={handleHeadingFontChange}
      />

      <FontSelector
        label="Body font"
        value={typography.bodyFontFamily}
        onChange={handleBodyFontChange}
      />

      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Base size
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {typography.baseFontSize}px
          </Typography>
        </Stack>
        <Slider
          value={typography.baseFontSize}
          onChange={handleBaseSizeChange}
          min={12}
          max={24}
          step={1}
          size="small"
          aria-label="Base font size"
          valueLabelDisplay="auto"
        />
      </Box>

      <TextField
        select
        label="Heading weight"
        value={String(typography.headingFontWeight)}
        onChange={handleHeadingWeightChange}
        size="small"
        fullWidth
      >
        {HEADING_WEIGHT_OPTIONS.map((option) => (
          <MenuItem key={option.value} value={String(option.value)}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>

      {/* Aa preview: decorative, hidden from assistive tech per 16.15. */}
      <Box>
        <Typography variant="caption" color="text.secondary" component="div">
          Preview
        </Typography>
        <Typography
          aria-hidden="true"
          sx={{
            fontFamily: `"${typography.headingFontFamily}", sans-serif`,
            fontSize: typography.baseFontSize * 2,
            fontWeight: typography.headingFontWeight,
            lineHeight: 1.1,
            mt: 0.5,
          }}
        >
          Aa
        </Typography>
      </Box>
    </Stack>
  );
};

export { TypographySection };
export default React.memo(TypographySection);
