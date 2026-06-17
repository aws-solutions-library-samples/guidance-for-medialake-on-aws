import React, { Component, useEffect, useMemo, type ReactNode } from "react";
import { Box, Typography } from "@mui/material";
import { EditorContent } from "@tiptap/react";
import DOMPurify from "dompurify";

import TiptapBubbleMenu from "./tiptap/TiptapBubbleMenu";
import { useTiptapEditor } from "./tiptap/useTiptapEditor";
// Bundle the Tiptap editor stylesheet (placeholder, ProseMirror padding,
// heading margins, link colors) alongside the component. Without this
// import the rich text surface would render unstyled.
import "./tiptap/tiptap.css";

/**
 * Props for {@link RichTextEditor}.
 *
 * Mirrors the `RichTextEditorProps` interface in design.md § "Key
 * TypeScript Interfaces" with one addition mandated by Requirement 16.7:
 * callers must pass an `ariaLabel` so screen readers announce the editor // i18n-ignore
 * with the pattern `"{field name} editor"` (e.g. "Title editor"). // i18n-ignore
 */
export interface RichTextEditorProps {
  /** Current HTML value. Rendered as the initial editor content. */
  value: string;
  /**
   * Called with the serialized HTML (`editor.getHTML()`) on every editor
   * transaction. Callers typically forward this into their Zustand store.
   */
  onChange: (html: string) => void;
  /** Placeholder text shown when the editor is empty. */
  placeholder?: string;
  /**
   * When `true`, the editor is constrained to a single line: headings,
   * lists, and hard breaks are disabled and pressing Enter is swallowed
   * (Requirement 8.11). Used for the portal title field.
   */
  singleLine?: boolean;
  /**
   * Minimum content height in pixels. Defaults to 96 to match the
   * outlined TextField rhythm described in `tiptap.css`.
   */
  minHeight?: number;
  /**
   * Optional feature flags for the bubble menu. Currently unused by the
   * implementation (the bubble menu renders its full toolbar) but kept
   * in the prop shape so `ContentSection` can opt into a narrower menu
   * in a follow-up without a breaking change.
   */
  features?: Array<"bold" | "italic" | "underline" | "link" | "heading" | "list" | "align">;
  /**
   * Accessible name for the outer textbox, e.g. `"Title editor"` or // i18n-ignore
   * `"Description editor"` (Requirement 16.7). This is forwarded to the // i18n-ignore
   * wrapper `Box` as `aria-label`, giving the editor an announceable
   * identity in screen readers.
   */
  ariaLabel: string;
}

/**
 * Props for the internal error boundary.
 *
 * The boundary wraps the live editor surface. When `useTiptapEditor`
 * throws (Requirement 8.12 / 8.13 — malformed incoming HTML is the
 * expected trigger), it renders the `fallback` node supplied by the
 * parent instead of crashing the page.
 */
interface EditorErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
}

interface EditorErrorBoundaryState {
  hasError: boolean;
}

/**
 * Class-based error boundary for the Tiptap editor surface.
 *
 * Hooks cannot be wrapped in a `try`/`catch` directly, so we rely on
 * React's error boundary contract: if `useTiptapEditor` throws during
 * render, React unmounts the subtree and calls `getDerivedStateFromError`
 * on the nearest boundary. The boundary then re-renders with the
 * parent-supplied fallback.
 *
 * We intentionally keep this boundary scoped to the single editor
 * instance so an error in one field (e.g. description) never knocks out
 * the other editors on the page.
 */
class EditorErrorBoundary extends Component<EditorErrorBoundaryProps, EditorErrorBoundaryState> {
  state: EditorErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): EditorErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown): void {
    // Log for operators; the fallback UI already tells the user what
    // happened and how to recover (design.md § "Scenario: Tiptap
    // initialization error").
    // eslint-disable-next-line no-console
    console.error("[RichTextEditor] Tiptap initialization error", error);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

/**
 * Inner editor body. Split from {@link RichTextEditor} so the call to
 * {@link useTiptapEditor} lives inside the error boundary's child tree.
 * If the hook throws, React unmounts this component and the boundary
 * catches the error; the outer `RichTextEditor` is unaffected.
 */
interface EditorBodyProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  singleLine?: boolean;
}

const EditorBody: React.FC<EditorBodyProps> = ({ value, onChange, placeholder, singleLine }) => {
  const editor = useTiptapEditor({
    content: value,
    placeholder,
    singleLine,
    onChange,
  });

  // Sync externally driven `value` changes into the editor (e.g. after a
  // preset is loaded or the store is re-initialized). We compare against
  // `editor.getHTML()` to avoid a feedback loop: every `setContent` call
  // emits a transaction that bubbles up through `onUpdate` and would
  // otherwise trigger an infinite re-render cycle.
  useEffect(() => {
    if (!editor) {
      return;
    }
    if (editor.getHTML() !== value) {
      // `emitUpdate = false` keeps the sync silent so we do not re-fire
      // `onChange` with the same HTML we just received from the parent.
      editor.commands.setContent(value, false);
    }
  }, [editor, value]);

  return (
    <>
      <TiptapBubbleMenu editor={editor} />
      <EditorContent editor={editor} />
    </>
  );
};

/**
 * RichTextEditor
 *
 * MUI-styled Tiptap wrapper used throughout the Portal Visual Editor.
 *
 * Behaviors (design.md § "Component Catalogue" row 8):
 *   1. Wraps {@link useTiptapEditor} so the editor instance, extensions,
 *      and `onUpdate` wiring live in one place.
 *   2. Renders {@link TiptapBubbleMenu} above the current selection for
 *      inline formatting.
 *   3. Accepts a `singleLine` prop that disables block-level features
 *      and swallows Enter (Requirement 8.11). Used by the title field.
 *   4. Forwards `ariaLabel` to the outer `Box` as `aria-label` so screen
 *      readers announce the editor with the pattern "{field} editor"
 *      (Requirement 16.7).
 *   5. If Tiptap throws during initialization (e.g. malformed incoming
 *      HTML), an internal error boundary catches the error and renders a
 *      read-only, DOMPurify-sanitized fallback with a notice advising
 *      the user to paste their content to recover (Requirement 8.12,
 *      8.13; design.md § "Scenario: Tiptap initialization error").
 */
const RichTextEditor: React.FC<RichTextEditorProps> = ({
  value,
  onChange,
  placeholder,
  singleLine,
  minHeight = 96,
  ariaLabel,
}) => {
  // Sanitize the current `value` for the fallback render path. Memoized
  // on `value` so we only recompute when the incoming HTML changes; this
  // also means a re-render that happens for unrelated reasons (e.g. the
  // Zustand store ticked) does not re-invoke DOMPurify.
  const sanitizedFallbackHtml = useMemo(() => DOMPurify.sanitize(value), [value]);

  // Fallback UI shown when the Tiptap initialization boundary trips.
  // Rendered as a read-only `dangerouslySetInnerHTML` block plus a small
  // `Typography` notice — deliberately not interactive so a corrupted
  // document cannot cascade into further errors.
  const fallback = (
    <Box>
      <Box
        sx={{ p: 1.5 }}
        // Preserve the original (sanitized) markup so the user can still
        // read their content even though they cannot edit it.
        dangerouslySetInnerHTML={{ __html: sanitizedFallbackHtml }}
      />
      <Typography variant="caption" color="warning.main" sx={{ display: "block", px: 1.5, pb: 1 }}>
        Content could not be edited - paste to fix
      </Typography>
    </Box>
  );

  return (
    <Box
      role="textbox"
      aria-label={ariaLabel}
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        minHeight,
        // Give the inner ProseMirror surface a flexible growth area while
        // still respecting the caller-supplied `minHeight` (Requirement
        // 8.2 — editor must accept a configurable minimum height).
        display: "flex",
        flexDirection: "column",
        "& .ProseMirror": {
          flex: 1,
          minHeight,
        },
      }}
    >
      <EditorErrorBoundary fallback={fallback}>
        <EditorBody
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          singleLine={singleLine}
        />
      </EditorErrorBoundary>
    </Box>
  );
};

export { RichTextEditor };
export default RichTextEditor;
