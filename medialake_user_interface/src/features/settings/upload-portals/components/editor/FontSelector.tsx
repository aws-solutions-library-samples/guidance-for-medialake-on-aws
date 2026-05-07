import React, { useCallback, useMemo } from "react";
import { Autocomplete, Box, TextField } from "@mui/material";

import { AVAILABLE_FONTS, type PortalFontOption } from "../../constants/fonts";
import { loadGoogleFont } from "../../utils/loadGoogleFont";

/**
 * Props for {@link FontSelector}.
 *
 * Mirrors design.md § "Key TypeScript Interfaces":
 *   - `value` is the currently selected font family (a string stored on
 *     `appearance.typography.headingFontFamily` or `bodyFontFamily`), not
 *     a {@link PortalFontOption} object. The component resolves the
 *     string against {@link AVAILABLE_FONTS} internally.
 *   - `onChange` receives the newly-selected family as a string so the
 *     caller can forward it straight into the Zustand store without
 *     worrying about option shape.
 */
export interface FontSelectorProps {
  /** Human-readable label rendered inside the `TextField`. */
  label: string;
  /** Current font family string (e.g. `"Inter"`). */
  value: string;
  /**
   * Called with the newly-selected family string. Invoked together with
   * `loadGoogleFont` so the corresponding stylesheet is fetched on the
   * same tick as the appearance mutation (Requirement 5.7).
   */
  onChange: (font: string) => void;
}

/**
 * Resolve a `value` string to its {@link PortalFontOption} entry from
 * {@link AVAILABLE_FONTS}. If the stored family is not in the curated list
 * (for example a portal authored before the current set was finalized),
 * synthesize a fallback option so the Autocomplete can still render the
 * current selection as-is instead of appearing empty.
 *
 * The synthesized option uses a neutral `"sans-serif"` CSS fallback —
 * enough to keep the dropdown entry legible without claiming knowledge
 * of a font we don't curate.
 */
function resolveFontOption(value: string): PortalFontOption {
  const match = AVAILABLE_FONTS.find((font) => font.family === value);
  if (match) {
    return match;
  }
  return { family: value, fallback: "sans-serif" };
}

/**
 * FontSelector
 *
 * Curated-font Autocomplete for the Typography section.
 *
 * Behavior highlights:
 *   1. Options are backed by the curated {@link AVAILABLE_FONTS} list
 *      (Requirement 5.5). Each rendered option shows its family name in
 *      its own font so users see a visual preview inline (Requirement
 *      5.6). Google Fonts are loaded lazily — the visual preview kicks
 *      in once the caller's `loadGoogleFont` effects run, which is fine
 *      for a curated list where families are pre-fetched by the
 *      surrounding Typography section on mount.
 *   2. The `value` prop is a family string. We resolve it to the
 *      matching curated entry via {@link resolveFontOption}; if the
 *      string is not curated (a portal saved with a legacy custom font),
 *      we synthesize an option so the Autocomplete still renders the
 *      current value instead of going blank.
 *   3. `disableClearable` keeps the underlying state non-nullable — a
 *      portal always has a selected font. This matches
 *      `PortalAppearanceTypography.headingFontFamily` /
 *      `bodyFontFamily` being required strings.
 *   4. On selection the component fires `onChange(family)` and
 *      immediately calls `loadGoogleFont(family)` so the stylesheet
 *      request races alongside the state update (Requirement 5.7).
 *      `loadGoogleFont` is itself idempotent and safely a no-op for
 *      system stacks, so calling it on every selection is safe.
 *   5. The `TextField` exposes `aria-label="{label} font family"` so
 *      screen readers announce the control with its typographic role
 *      (Requirement 16.6). Keeping `label` as a visual label and
 *      duplicating in `aria-label` matches the ColorPicker / spec
 *      pattern and keeps the control discoverable when the visual
 *      label is clipped.
 */
const FontSelector: React.FC<FontSelectorProps> = ({ label, value, onChange }) => {
  const selected = useMemo(() => resolveFontOption(value), [value]);

  const ariaLabel = useMemo(() => `${label} font family`, [label]);

  const handleChange = useCallback(
    (_event: React.SyntheticEvent, newValue: PortalFontOption | null) => {
      // `disableClearable` ensures `newValue` is never null at runtime,
      // but MUI's typings still allow `null` in the handler signature.
      // We narrow defensively so invalid clear attempts are silently
      // ignored rather than propagating `onChange("")` upstream.
      if (!newValue) {
        return;
      }
      onChange(newValue.family);
      loadGoogleFont(newValue.family);
    },
    [onChange]
  );

  return (
    <Autocomplete<PortalFontOption, false, true, false>
      options={AVAILABLE_FONTS as PortalFontOption[]}
      value={selected}
      onChange={handleChange}
      getOptionLabel={(option) => option.family}
      isOptionEqualToValue={(a, b) => a.family === b.family}
      disableClearable
      renderOption={(props, option) => {
        // Destructure `key` out so React's warning about keys spread via
        // props goes away; MUI passes a stable key through `props.key`.
        const { key, ...liProps } = props as React.HTMLAttributes<HTMLLIElement> & {
          key: React.Key;
        };
        return (
          <Box
            component="li"
            key={key}
            {...liProps}
            sx={{
              fontFamily: `"${option.family}", ${option.fallback}`,
            }}
          >
            {option.family}
          </Box>
        );
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          inputProps={{
            ...params.inputProps,
            "aria-label": ariaLabel,
          }}
        />
      )}
    />
  );
};

export { FontSelector };
export default FontSelector;
