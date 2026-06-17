import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, ButtonBase, Popover, Stack, TextField, Typography } from "@mui/material";
import { HexColorPicker } from "react-colorful";

import { HEX_COLOR_RE } from "../../schemas/appearance.schema";

/**
 * Props for {@link ColorPicker}.
 *
 * Shape mirrors design.md § "Key TypeScript Interfaces".
 */
export interface ColorPickerProps {
  /** Human-readable label shown next to the swatch (e.g. "Primary"). */
  label: string;
  /** Current color value (hex string like `"#ff0000"`). */
  value: string;
  /**
   * Called with the new color after a 100ms debounce. Local state always
   * updates immediately so drag feedback stays snappy; this callback is
   * invoked only once per 100ms quiescence window (see Requirement 4.6).
   */
  onChange: (color: string) => void;
  /**
   * Optional preset swatches rendered as clickable circles. When empty or
   * omitted the presets row is hidden entirely.
   */
  presets?: string[];
}

/**
 * Debounce window (ms) before a local-state color change is propagated to
 * `onChange`. Chosen to match Requirement 4.6 — 100ms is tight enough to
 * feel instantaneous while still coalescing the high-frequency updates
 * `react-colorful` emits during drag.
 */
const ONCHANGE_DEBOUNCE_MS = 100;

/**
 * ColorPicker
 *
 * Compact swatch-style color input used throughout `AppearanceSection`.
 *
 * Interaction model:
 *   1. The visible trigger is a small square button whose background is the
 *      current `value`. Its accessible name follows the pattern
 *      `"Change {label} color, currently {value}"` (Requirement 16.4). // i18n-ignore
 *   2. Clicking the swatch opens a MUI `Popover` anchored to it containing
 *      a `react-colorful` `HexColorPicker`, a hex `TextField`, an optional
 *      presets row, and a Reset link.
 *   3. While the popover is open, the color picker and hex field are both
 *      backed by local React state so drag updates feel instant. Upstream
 *      `onChange` is called on a 100ms debounce (Requirement 4.6) and any
 *      pending debounce is flushed when the popover closes.
 *   4. Invalid hex text (anything not matching the module-level
 *      `HEX_COLOR_RE` regex exported from the Zod schema) is rejected on
 *      blur — the input reverts to the last valid value, matching
 *      Requirement 4.8.
 *   5. Click-away or Escape closes the popover and restores focus to the
 *      trigger button (Requirement 4.9 / 16.11 / 16.13). MUI's `Popover`
 *      handles both dismissal paths; explicit `onClose` wiring ensures
 *      focus restoration.
 *   6. The popover re-initializes its local state from the latest `value`
 *      prop every time it re-opens so external mutations (e.g. preset
 *      schemes applied from another control) remain authoritative.
 */
const ColorPicker: React.FC<ColorPickerProps> = ({ label, value, onChange, presets }) => {
  // Anchor / open state for the MUI Popover.
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const isOpen = anchorEl !== null;

  // The snapshot of `value` captured at popover-open time. Used by the
  // Reset link so "reset" means "back to where I was when I opened this
  // popover", not "back to the application-wide defaults" (that is a
  // separate action owned by `AppearanceSection`).
  const [initialValue, setInitialValue] = useState<string>(value);

  // Local state powering both the HexColorPicker and the hex TextField.
  // Kept strictly in sync with what the user is currently looking at so
  // the UI stays snappy even when the outer `onChange` is debounced.
  const [localColor, setLocalColor] = useState<string>(value);

  // Separate buffer for the hex TextField so partial typing (like "#ab")
  // does not clobber `localColor` until validation passes on blur.
  const [hexInput, setHexInput] = useState<string>(value);

  // Debounce timer tracked across renders without retriggering effects.
  // `window.setTimeout` returns `number` in the browser / jsdom; typed as
  // `number | null` to match the exact contract.
  const debounceTimerRef = useRef<number | null>(null);

  // Stash the latest `onChange` prop in a ref so the debounced callback
  // always fires the caller's current handler (avoids stale closures if
  // the parent swaps handlers between renders, and lets us leave the
  // debounce setter's dependency list intentionally minimal).
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  /**
   * Clear any pending debounce. Called on unmount, on popover close, and
   * before scheduling a fresh debounce so we only ever have at most one
   * timer in flight at a time.
   */
  const clearDebounce = useCallback(() => {
    if (debounceTimerRef.current !== null) {
      window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
  }, []);

  /**
   * Flush any pending debounce immediately by firing `onChange` with the
   * most recent local color. Invoked when the popover is about to close
   * so the caller never loses the final drag frame.
   */
  const flushDebounce = useCallback((finalColor: string) => {
    if (debounceTimerRef.current !== null) {
      window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
      onChangeRef.current(finalColor);
    }
  }, []);

  /**
   * Schedule a debounced `onChange` with `newColor`. Replaces any already
   * pending timer so rapid successive changes coalesce into exactly one
   * upstream update after 100ms of quiescence.
   */
  const scheduleDebouncedChange = useCallback(
    (newColor: string) => {
      clearDebounce();
      debounceTimerRef.current = window.setTimeout(() => {
        debounceTimerRef.current = null;
        onChangeRef.current(newColor);
      }, ONCHANGE_DEBOUNCE_MS);
    },
    [clearDebounce]
  );

  // Clean up any in-flight timer if the component unmounts while one is
  // pending. Without this the debounce could fire after unmount and try
  // to call a stale handler against an unmounted parent tree.
  useEffect(() => {
    return () => {
      clearDebounce();
    };
  }, [clearDebounce]);

  /**
   * Open the popover: anchor to the trigger, capture the current `value`
   * as the "reset point", and re-seed local state from the latest prop.
   */
  const handleOpen = useCallback(() => {
    if (triggerRef.current) {
      setAnchorEl(triggerRef.current);
      setInitialValue(value);
      setLocalColor(value);
      setHexInput(value);
    }
  }, [value]);

  /**
   * Close the popover. Flushes any pending debounce so the final color
   * always reaches the caller, then clears the anchor (MUI's `Popover`
   * restores focus to the anchor element automatically on close, which
   * satisfies Requirement 16.13).
   */
  const handleClose = useCallback(() => {
    flushDebounce(localColor);
    setAnchorEl(null);
  }, [flushDebounce, localColor]);

  /**
   * Update local state immediately (so the UI repaints this frame) and
   * schedule a debounced upstream notification.
   */
  const handleColorChange = useCallback(
    (newColor: string) => {
      setLocalColor(newColor);
      setHexInput(newColor);
      scheduleDebouncedChange(newColor);
    },
    [scheduleDebouncedChange]
  );

  /**
   * Keystroke handler for the hex TextField: accept whatever the user
   * types into the buffer without validation so partial inputs (like
   * `#ab`) are not clobbered mid-typing.
   */
  const handleHexChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setHexInput(event.target.value);
  }, []);

  /**
   * Validate the hex TextField on blur. Valid values (matching
   * `HEX_COLOR_RE`) flow through the same debounced pipeline as a
   * color-picker drag. Invalid values are rejected — the buffer snaps
   * back to the last known good color (Requirement 4.8).
   */
  const handleHexBlur = useCallback(() => {
    if (HEX_COLOR_RE.test(hexInput)) {
      handleColorChange(hexInput);
    } else {
      setHexInput(localColor);
    }
  }, [handleColorChange, hexInput, localColor]);

  /**
   * Pressing Enter inside the hex TextField acts like a blur: commit the
   * value (or revert if invalid) without closing the popover.
   */
  const handleHexKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleHexBlur();
      }
    },
    [handleHexBlur]
  );

  /**
   * Preset swatch click: apply the preset to local state and notify the
   * debounced pipeline (same contract as a drag).
   */
  const handlePresetClick = useCallback(
    (preset: string) => {
      handleColorChange(preset);
    },
    [handleColorChange]
  );

  /**
   * Reset link click: restore local state to whatever `value` was when
   * the popover opened. Firing through the debounced pipeline means a
   * reset-then-close still produces one upstream `onChange` invocation.
   */
  const handleReset = useCallback(() => {
    handleColorChange(initialValue);
  }, [handleColorChange, initialValue]);

  // Accessible name for the swatch trigger. Using `useMemo` keeps the
  // string stable across re-renders with unchanged inputs so screen
  // readers do not re-announce on every parent update.
  const triggerAriaLabel = useMemo(
    () => `Change ${label} color, currently ${value}`,
    [label, value]
  );

  const hasPresets = Array.isArray(presets) && presets.length > 0;

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1}>
        <ButtonBase
          ref={triggerRef}
          onClick={handleOpen}
          aria-label={triggerAriaLabel}
          aria-haspopup="dialog"
          aria-expanded={isOpen}
          focusRipple
          sx={{
            width: 32,
            height: 32,
            borderRadius: 1,
            border: "1px solid",
            borderColor: "divider",
            backgroundColor: value,
            flexShrink: 0,
          }}
        />
        <Typography variant="body2" component="span">
          {label}
        </Typography>
      </Stack>

      <Popover
        open={isOpen}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        slotProps={{
          paper: {
            sx: { p: 2, width: 240 },
          },
        }}
      >
        <Stack spacing={1.5}>
          <HexColorPicker color={localColor} onChange={handleColorChange} />

          <TextField
            value={hexInput}
            onChange={handleHexChange}
            onBlur={handleHexBlur}
            onKeyDown={handleHexKeyDown}
            size="small"
            fullWidth
            label="Hex"
            inputProps={{
              "aria-label": "Hex color value",
              spellCheck: false,
              autoComplete: "off",
            }}
          />

          {hasPresets && (
            <Stack
              direction="row"
              spacing={0.75}
              flexWrap="wrap"
              useFlexGap
              aria-label="Preset colors"
            >
              {presets!.map((preset) => (
                <ButtonBase
                  key={preset}
                  onClick={() => handlePresetClick(preset)}
                  aria-label={`Preset ${preset}`}
                  focusRipple
                  sx={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    border: "1px solid",
                    borderColor: "divider",
                    backgroundColor: preset,
                  }}
                />
              ))}
            </Stack>
          )}

          <Box>
            <Button onClick={handleReset} size="small" variant="text" sx={{ px: 0.5, minWidth: 0 }}>
              Reset
            </Button>
          </Box>
        </Stack>
      </Popover>
    </Box>
  );
};

export { ColorPicker };
export default ColorPicker;
