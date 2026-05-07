import React, { Suspense, lazy } from "react";
import { Box, Skeleton } from "@mui/material";

import type { RichTextEditorProps } from "./RichTextEditor";

/**
 * Code-split entry point for the portal editor rich-text editor.
 *
 * The underlying {@link RichTextEditor} component pulls in the full
 * Tiptap stack (`@tiptap/react` + five extensions, ~35 KB gzipped) plus
 * DOMPurify (~7 KB). Splitting it behind `React.lazy` keeps those bytes
 * out of the initial editor chunk; they only load when the Content
 * sidebar section mounts — the first time the admin edits a rich-text
 * field.
 *
 * Consumers import this file instead of `./RichTextEditor` directly so
 * the split is transparent. The inner `RichTextEditor` remains
 * importable at `./RichTextEditor` for tests (they render synchronously
 * with a mocked Tiptap hook).
 */
const LazyRichTextEditor = lazy(() =>
  import("./RichTextEditor").then((m) => ({ default: m.default }))
);

/**
 * Fallback rendered while Tiptap is fetched. Mirrors the outer shape of
 * the real editor (bordered `Box` with a caller-configurable minHeight)
 * so the sidebar's vertical rhythm stays stable across the load boundary.
 */
const RichTextEditorFallback: React.FC<{ minHeight?: number }> = ({ minHeight }) => (
  <Box
    sx={{
      border: "1px solid",
      borderColor: "divider",
      borderRadius: 1,
      minHeight: minHeight ?? 96,
      p: 1,
    }}
  >
    <Skeleton variant="text" width="60%" />
    <Skeleton variant="text" width="40%" />
  </Box>
);

/**
 * Lazy-loaded {@link RichTextEditor}. Exposes the same props surface as
 * the eager component.
 */
const RichTextEditorLazy: React.FC<RichTextEditorProps> = (props) => (
  <Suspense fallback={<RichTextEditorFallback minHeight={props.minHeight} />}>
    <LazyRichTextEditor {...props} />
  </Suspense>
);

export { RichTextEditorLazy };
export default RichTextEditorLazy;
