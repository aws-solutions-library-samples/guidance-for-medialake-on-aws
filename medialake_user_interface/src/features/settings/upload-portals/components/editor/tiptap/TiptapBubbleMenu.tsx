import React from "react";
import { BubbleMenu, type Editor } from "@tiptap/react";
import { IconButton, Paper, Stack } from "@mui/material";
import FormatAlignCenterIcon from "@mui/icons-material/FormatAlignCenter";
import FormatAlignLeftIcon from "@mui/icons-material/FormatAlignLeft";
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import LinkIcon from "@mui/icons-material/Link";

/**
 * Props for {@link TiptapBubbleMenu}.
 *
 * Receives the already-constructed Tiptap editor (from {@link useTiptapEditor})
 * and renders a floating toolbar above the current selection. When `editor`
 * is `null` (pre-hydration / SSR / error fallback) the menu renders nothing.
 */
export interface TiptapBubbleMenuProps {
  editor: Editor | null;
}

/**
 * Tiptap BubbleMenu rendered with MUI primitives.
 *
 * Shown floating above the current selection when the user highlights text
 * inside a `RichTextEditor`. The toolbar exposes the minimal formatting set
 * called out in design.md § "TiptapBubbleMenu" (Requirement 8.8): bold,
 * italic, underline, link, align-left, align-center.
 *
 * Behaviors:
 *   1. The Link button is a deliberately basic stub — it sets a placeholder
 *      `https://` href rather than opening a URL prompt dialog. The design
 *      explicitly accepts this for the initial implementation; a richer UX
 *      (modal URL input, keyboard shortcut) is out of scope for task 3.3.
 *   2. All command chains are wrapped in `.focus()` so the editor retains
 *      focus after a toolbar interaction. Without this, clicking an icon
 *      button would blur the editor and collapse the selection.
 *   3. Every `IconButton` carries an `aria-label` so assistive tech can
 *      identify the control (Requirement 17.5). Labels mirror the visual
 *      icons and match the style used elsewhere in the editor surface.
 *   4. The component is wrapped in `React.memo` (the exported value) so
 *      parent re-renders caused by unrelated store mutations do not rebuild
 *      the floating toolbar every tick.
 *
 * @param editor Tiptap editor instance, or `null` while the editor is still
 *               initializing. Returning `null` early keeps the render pass
 *               free of `editor!` non-null assertions downstream.
 */
const TiptapBubbleMenuImpl: React.FC<TiptapBubbleMenuProps> = ({ editor }) => {
  if (!editor) {
    return null;
  }

  const handleBold = () => {
    editor.chain().focus().toggleBold().run();
  };

  const handleItalic = () => {
    editor.chain().focus().toggleItalic().run();
  };

  const handleUnderline = () => {
    editor.chain().focus().toggleUnderline().run();
  };

  // Stubbed link handler: set a placeholder href so the selection becomes
  // clickable markup. The design doc (§ "TiptapBubbleMenu") expressly allows
  // a basic implementation here; Phase 6 can revisit with a URL prompt.
  const handleLink = () => {
    editor.chain().focus().setLink({ href: "https://" }).run();
  };

  const handleAlignLeft = () => {
    editor.chain().focus().setTextAlign("left").run();
  };

  const handleAlignCenter = () => {
    editor.chain().focus().setTextAlign("center").run();
  };

  return (
    <BubbleMenu editor={editor}>
      <Paper
        elevation={3}
        sx={{
          display: "inline-flex",
          p: 0.25,
          borderRadius: 1,
        }}
      >
        <Stack direction="row" spacing={0.25}>
          <IconButton size="small" aria-label="Bold" onClick={handleBold}>
            <FormatBoldIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" aria-label="Italic" onClick={handleItalic}>
            <FormatItalicIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" aria-label="Underline" onClick={handleUnderline}>
            <FormatUnderlinedIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" aria-label="Link" onClick={handleLink}>
            <LinkIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" aria-label="Align left" onClick={handleAlignLeft}>
            <FormatAlignLeftIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" aria-label="Align center" onClick={handleAlignCenter}>
            <FormatAlignCenterIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Paper>
    </BubbleMenu>
  );
};

/**
 * Memoized export. See the component-level docblock for why memoization
 * matters here (parent re-renders on unrelated store changes).
 */
export const TiptapBubbleMenu = React.memo(TiptapBubbleMenuImpl);

export default TiptapBubbleMenu;
