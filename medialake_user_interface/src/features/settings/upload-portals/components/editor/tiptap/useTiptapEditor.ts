import { useCallback } from "react";
import { useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";

/**
 * Options for {@link useTiptapEditor}.
 *
 * Matches design.md § "Tiptap integration" and Requirements 8.1, 8.2, 8.9,
 * 8.10, 8.11:
 *   - `content`   initial HTML loaded into the editor
 *   - `placeholder` optional placeholder text rendered when the document is empty
 *   - `singleLine` when `true`, headings / lists / hard breaks are stripped from
 *     StarterKit and `Enter` is intercepted to prevent line breaks (used for the
 *     title field)
 *   - `onChange`  called with `editor.getHTML()` on every transaction so the
 *     caller can persist the HTML into the Zustand store
 */
export interface UseTiptapEditorOptions {
  /** Initial HTML content. Passed straight to Tiptap's `content` option. */
  content: string;
  /** Placeholder text shown when the editor is empty. */
  placeholder?: string;
  /**
   * When true, the editor is constrained to a single line:
   *   - heading / bulletList / orderedList / hardBreak extensions are disabled
   *   - pressing Enter is swallowed so no paragraph break or hard break inserts
   */
  singleLine?: boolean;
  /** Invoked with the serialized HTML on every transaction. */
  onChange: (html: string) => void;
}

/**
 * URL scheme validator for the Link extension.
 *
 * Tiptap's Link extension exposes a legacy `validate` hook that is consulted
 * by the auto-linker. We reject `javascript:` URLs defensively (Requirement
 * 8.10) so user-pasted links can never inject script execution. This is the
 * first line of defense; DOMPurify at render time is the second.
 */
const isNotJavascriptUrl = (url: string): boolean => !/^javascript:/i.test(url);

/**
 * Create a Tiptap editor instance tailored for the Portal Visual Editor.
 *
 * This is a thin wrapper around `useEditor` that wires up the exact
 * extension set documented in the design:
 *   - `StarterKit` with headings disabled in `singleLine` mode and
 *     block-level extensions (blockquote / codeBlock / code) turned off
 *   - `Underline`
 *   - `Link` with `openOnClick: false`, safe `rel` / `target` attributes,
 *     and a `javascript:` URL rejector
 *   - `Placeholder` taking the caller-supplied string
 *   - `TextAlign` scoped to heading and paragraph nodes
 *
 * The hook returns `Editor | null` to match Tiptap's own SSR-safe contract;
 * callers must render a skeleton / disabled state while `editor` is `null`.
 *
 * @returns The Tiptap editor instance, or `null` on the first render pass
 *          before the editor is fully instantiated.
 */
export function useTiptapEditor(options: UseTiptapEditorOptions): Editor | null {
  const { content, placeholder, singleLine = false, onChange } = options;

  // Keep the `onChange` reference stable across renders via a useCallback
  // shell so Tiptap's internal update listener does not need to be rebuilt
  // on every parent re-render. Tiptap re-uses the editor instance across
  // renders, so this only meaningfully matters for the initial mount, but
  // it keeps the hook's contract simple and predictable.
  const handleUpdate = useCallback(
    ({ editor }: { editor: Editor }) => {
      onChange(editor.getHTML());
    },
    [onChange]
  );

  return useEditor({
    content,
    extensions: [
      StarterKit.configure({
        // In `singleLine` mode we strip every block-level extension that
        // would produce newlines or structural children. Outside
        // `singleLine`, `heading` is restricted to H2/H3 because the
        // toolbar UI in the design exposes only those two levels; H1 is
        // reserved for the portal title rendered by `PortalHeader`.
        heading: singleLine ? false : { levels: [2, 3] },
        bulletList: singleLine ? false : undefined,
        orderedList: singleLine ? false : undefined,
        hardBreak: singleLine ? false : undefined,
        // These are always disabled — design.md does not expose them in the
        // bubble menu and they would produce ugly fallback rendering in the
        // MUI-styled preview.
        blockquote: false,
        codeBlock: false,
        code: false,
      }),
      Underline,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          rel: "noopener noreferrer",
          target: "_blank",
        },
        // The legacy `validate` hook is still honored by the extension
        // (see `@tiptap/extension-link/dist/link.d.ts`) and gives us a
        // simple way to reject `javascript:` URLs from the auto-linker.
        validate: isNotJavascriptUrl,
      }),
      Placeholder.configure({
        placeholder: placeholder ?? "",
      }),
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
    ],
    // Swallow Enter when `singleLine` is true. Returning `true` from
    // `handleKeyDown` tells ProseMirror we've consumed the event, which
    // prevents both the default paragraph split and any hard-break
    // extension from firing.
    editorProps: singleLine
      ? {
          handleKeyDown: (_view, event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              return true;
            }
            return false;
          },
        }
      : undefined,
    onUpdate: handleUpdate,
  });
}

export default useTiptapEditor;
