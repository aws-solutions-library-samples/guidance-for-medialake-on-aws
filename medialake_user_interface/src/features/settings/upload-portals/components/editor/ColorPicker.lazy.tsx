import React, { Suspense, lazy } from "react";
import { Box, Skeleton } from "@mui/material";

import type { ColorPickerProps } from "./ColorPicker";

/**
 * Code-split entry point for the portal editor color picker.
 *
 * The underlying {@link ColorPicker} component pulls in `react-colorful`
 * (~3 KB gzipped) and a small MUI `Popover` surface. Splitting it behind
 * `React.lazy` keeps those bytes out of the initial editor chunk and
 * loads them on demand when the first color swatch renders — which only
 * happens when the Appearance sidebar section is expanded.
 *
 * Consumers import this file instead of `./ColorPicker` directly so the
 * split is transparent. The inner `ColorPicker` remains importable at
 * `./ColorPicker` for tests (they render the component synchronously).
 */
const LazyColorPicker = lazy(() => import("./ColorPicker").then((m) => ({ default: m.default })));

/**
 * Fallback rendered while the lazy chunk loads. Sized and shaped to match
 * the swatch + label row so the sidebar layout doesn't jump when the real
 * component mounts. 32 px square tracks the `ColorPicker` trigger width.
 */
const ColorPickerFallback: React.FC<{ label: string }> = ({ label }) => (
  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
    <Skeleton variant="rounded" width={32} height={32} />
    <Skeleton variant="text" width={80}>
      <span>{label}</span>
    </Skeleton>
  </Box>
);

/**
 * Lazy-loaded {@link ColorPicker}. Exposes the same props surface as the
 * eager component; a minimal `Suspense` boundary renders a skeleton
 * while `react-colorful` is fetched.
 */
const ColorPickerLazy: React.FC<ColorPickerProps> = (props) => (
  <Suspense fallback={<ColorPickerFallback label={props.label} />}>
    <LazyColorPicker {...props} />
  </Suspense>
);

export { ColorPickerLazy };
export default ColorPickerLazy;
