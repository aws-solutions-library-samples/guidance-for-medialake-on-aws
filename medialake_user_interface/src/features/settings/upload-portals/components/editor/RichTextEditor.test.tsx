/**
 * Unit tests for RichTextEditor.
 *
 * **Validates: Requirements 8.2, 8.11, 8.12**
 *
 * Coverage (design.md § "Unit Tests - `RichTextEditor.test.tsx`"):
 *   1. Initial HTML renders — `value="<p>Hello</p>"` shows "Hello".
 *   2. `onChange` receives the HTML from `editor.getHTML()` when the
 *      hook's `onUpdate` fires.
 *   3. The `placeholder` prop is forwarded into `useTiptapEditor`.
 *   4. The `singleLine` prop is forwarded into `useTiptapEditor`.
 *   5. If `useTiptapEditor` throws, the error fallback renders the
 *      DOMPurify-sanitized HTML plus the
 *      "Content could not be edited - paste to fix" notice.
 *   6. The outer `Box` carries the caller-supplied `ariaLabel`.
 *
 * Strategy: the Tiptap stack is mocked module-wide so tests do not spin
 * up a real ProseMirror view. The mock `useTiptapEditor` lets each test
 * configure what the hook returns (a fake editor, nothing, or a thrown
 * error). The mocked `EditorContent` renders the initial HTML the hook
 * was seeded with so the "initial HTML renders" assertion is meaningful.
 */

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { render, screen } from "@testing-library/react";

import RichTextEditor from "./RichTextEditor";
import { useTiptapEditor } from "./tiptap/useTiptapEditor";

/**
 * Mock the Tiptap hook. Each test reconfigures the mock implementation
 * via `vi.mocked(useTiptapEditor).mockImplementation(...)` so we can
 * control both what editor shape it returns AND the arguments it was
 * called with (useful for placeholder / singleLine forwarding checks).
 */
vi.mock("./tiptap/useTiptapEditor", () => ({
  useTiptapEditor: vi.fn(),
}));

/**
 * Mock `@tiptap/react` so `EditorContent` and `BubbleMenu` are cheap
 * stand-ins that render a visible stub referencing the `editor` prop.
 * This keeps the tests rendering something meaningful while avoiding
 * the heavy ProseMirror initialization that only works reliably in a
 * real browser environment.
 */
vi.mock("@tiptap/react", async () => {
  const actual = await vi.importActual<typeof import("@tiptap/react")>("@tiptap/react");
  return {
    ...actual,
    EditorContent: ({ editor }: { editor: { getHTML: () => string } | null }) => (
      <div
        data-testid="editor-content"
        // Reflect the initial HTML the hook was seeded with so the first
        // render assertion ("Hello" is visible) is exercised through the
        // same DOM path the real EditorContent would use.
        dangerouslySetInnerHTML={{
          __html: editor ? editor.getHTML() : "",
        }}
      />
    ),
    BubbleMenu: ({ children }: { children?: React.ReactNode }) => (
      <div data-testid="bubble-menu">{children}</div>
    ),
  };
});

/**
 * Build a minimal fake Tiptap editor with the subset of surface used
 * by {@link RichTextEditor}. `getHTML` returns whatever content we seed
 * (typically the initial `value`); `commands.setContent` is a no-op spy
 * so the sync effect can invoke it without blowing up.
 */
function createFakeEditor(html: string) {
  return {
    getHTML: vi.fn(() => html),
    commands: {
      setContent: vi.fn(),
    },
  };
}

describe("RichTextEditor", () => {
  beforeEach(() => {
    vi.mocked(useTiptapEditor).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the initial HTML value", () => {
    const editor = createFakeEditor("<p>Hello</p>");
    vi.mocked(useTiptapEditor).mockReturnValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      editor as any
    );

    render(<RichTextEditor value="<p>Hello</p>" onChange={() => {}} ariaLabel="Title editor" />);

    // The mocked EditorContent reflects `editor.getHTML()` into the DOM,
    // so the caller-visible content includes "Hello".
    expect(screen.getByTestId("editor-content")).toHaveTextContent("Hello");
  });

  it("invokes onChange with the HTML from editor.getHTML() when the hook's onUpdate fires", () => {
    const onChange = vi.fn();
    const editor = createFakeEditor("<p>Hello</p>");

    // Capture the options passed to the hook so we can invoke the
    // caller-supplied `onChange` in the exact same way the real hook
    // would on a Tiptap transaction.
    let capturedOnChange: ((html: string) => void) | undefined;
    vi.mocked(useTiptapEditor).mockImplementation((opts) => {
      capturedOnChange = opts.onChange;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return editor as any;
    });

    render(<RichTextEditor value="<p>Hello</p>" onChange={onChange} ariaLabel="Title editor" />);

    // Simulate Tiptap calling `onUpdate({ editor })`, which the hook
    // internally forwards as `onChange(editor.getHTML())`.
    expect(capturedOnChange).toBeDefined();
    editor.getHTML.mockReturnValue("<p>Updated</p>");
    capturedOnChange!(editor.getHTML());

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("<p>Updated</p>");
  });

  it("forwards `placeholder` into useTiptapEditor", () => {
    vi.mocked(useTiptapEditor).mockReturnValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      createFakeEditor("") as any
    );

    render(
      <RichTextEditor
        value=""
        onChange={() => {}}
        placeholder="Type here"
        ariaLabel="Title editor"
      />
    );

    const call = (useTiptapEditor as unknown as Mock).mock.calls[0][0];
    expect(call.placeholder).toBe("Type here");
  });

  it("forwards `singleLine` into useTiptapEditor", () => {
    vi.mocked(useTiptapEditor).mockReturnValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      createFakeEditor("") as any
    );

    render(<RichTextEditor value="" onChange={() => {}} singleLine ariaLabel="Title editor" />);

    const call = (useTiptapEditor as unknown as Mock).mock.calls[0][0];
    expect(call.singleLine).toBe(true);
  });

  it("applies the caller-supplied ariaLabel to the outer textbox", () => {
    vi.mocked(useTiptapEditor).mockReturnValue(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      createFakeEditor("") as any
    );

    render(<RichTextEditor value="" onChange={() => {}} ariaLabel="Description editor" />);

    expect(screen.getByRole("textbox", { name: "Description editor" })).toBeInTheDocument();
  });

  it("renders the error fallback with the sanitized HTML and notice when useTiptapEditor throws", () => {
    // Silence the expected React + componentDidCatch error logs so the
    // test output stays clean; `console.error` would otherwise fire
    // multiple times while React unwinds the boundary.
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    vi.mocked(useTiptapEditor).mockImplementation(() => {
      throw new Error("boom");
    });

    // Include a tag DOMPurify should preserve ("<b>") and a tag it should
    // strip ("<script>") so we can assert the fallback output actually
    // flows through sanitization.
    const dangerous = "<b>Safe</b><script>alert('xss')</script>";

    render(<RichTextEditor value={dangerous} onChange={() => {}} ariaLabel="Title editor" />);

    // The notice text is present verbatim.
    expect(screen.getByText("Content could not be edited - paste to fix")).toBeInTheDocument();

    // The sanitized content survived — "Safe" is still visible.
    expect(screen.getByText("Safe")).toBeInTheDocument();

    // And the dangerous `<script>` tag was stripped by DOMPurify before
    // it was written into the DOM.
    expect(document.querySelector("script")).toBeNull();

    errorSpy.mockRestore();
  });
});
