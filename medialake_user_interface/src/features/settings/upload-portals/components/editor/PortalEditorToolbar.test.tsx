/**
 * Unit tests for PortalEditorToolbar.
 *
 * **Validates: Requirements 10.2, 10.4**
 *
 * Coverage:
 *   1. Default render (not dirty, not saving, edit mode): Save is
 *      disabled, dirty indicator is absent, Back button renders with
 *      `aria-label="Back to portals"` (Requirement 10.2 — Save gating).
 *   2. `isDirty={true}`: Save becomes enabled and the dirty indicator
 *      ("Unsaved changes") appears (Requirement 10.2).
 *   3. `isCreateMode={true}`: breadcrumb reads "New Portal" and the
 *      Preview button is disabled (no public URL yet — Requirement
 *      10.15 cross-check).
 *   4. `isCreateMode={false}` with a portal name: breadcrumb mirrors the
 *      name verbatim.
 *   5. `onPublish` fires exactly once when Publish is clicked. The
 *      toolbar itself is dumb — the `isActive: true` flip happens at
 *      the PortalEditorPage layer, so this test only verifies the
 *      handler is invoked (Requirement 10.4).
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import PortalEditorToolbar, { type PortalEditorToolbarProps } from "./PortalEditorToolbar";

/**
 * Build a props object filled with no-op handlers and sensible defaults.
 * Individual tests override the fields they care about so each case only
 * states what matters for the assertion at hand.
 */
const buildProps = (
  overrides: Partial<PortalEditorToolbarProps> = {}
): PortalEditorToolbarProps => ({
  portalName: "",
  isCreateMode: false,
  isDirty: false,
  isSaving: false,
  onSave: vi.fn(),
  onPublish: vi.fn(),
  onPreviewInNewTab: vi.fn(),
  onBack: vi.fn(),
  ...overrides,
});

describe("PortalEditorToolbar", () => {
  it("disables Save, hides the dirty indicator, and exposes the Back button by default", () => {
    render(<PortalEditorToolbar {...buildProps({ portalName: "Demo Portal" })} />);

    // Save is disabled because `isDirty` is false.
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    // Dirty indicator is rendered as an `aria-label="Unsaved changes"`
    // span; it should not be in the DOM when the form is clean.
    expect(screen.queryByLabelText("Unsaved changes")).not.toBeInTheDocument();

    // Back button is present with the documented aria-label.
    expect(screen.getByRole("button", { name: "Back to portals" })).toBeInTheDocument();
  });

  it("enables Save and shows the dirty indicator when isDirty is true", () => {
    render(<PortalEditorToolbar {...buildProps({ portalName: "Demo Portal", isDirty: true })} />);

    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    expect(screen.getByLabelText("Unsaved changes")).toBeInTheDocument();
  });

  it("renders the `New Portal` breadcrumb and disables Preview in create mode", () => {
    render(<PortalEditorToolbar {...buildProps({ isCreateMode: true })} />);

    expect(screen.getByText("New Portal")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /preview/i })).toBeDisabled();
  });

  it("renders the portal name as the breadcrumb in edit mode", () => {
    render(
      <PortalEditorToolbar {...buildProps({ isCreateMode: false, portalName: "My Portal" })} />
    );

    expect(screen.getByText("My Portal")).toBeInTheDocument();
  });

  it("invokes onPublish exactly once when Publish is clicked", async () => {
    const onPublish = vi.fn();
    const user = userEvent.setup();

    render(<PortalEditorToolbar {...buildProps({ portalName: "Demo Portal", onPublish })} />);

    await user.click(screen.getByRole("button", { name: "Publish" }));

    expect(onPublish).toHaveBeenCalledTimes(1);
  });
});
