import { beforeEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material";

import { usePortalEditorStore } from "@/features/settings/upload-portals/stores/usePortalEditorStore";

import { MetadataSection } from "./MetadataSection";

/**
 * Coverage for the "Require form submission" toggle added to MetadataSection.
 *
 * The toggle drives the per-portal `formSubmissionEnabled` flag: when ON
 * (default) the public portal shows a Submit step; when OFF the portal is
 * upload-only and `formSubmissionComplete` is always false downstream.
 *
 * The section renders exactly one checkbox — the MUI Switch. Its input is
 * visually hidden by MUI's CSS, so we query the DOM node directly rather than
 * relying on accessible-role resolution under jsdom.
 */

const theme = createTheme();

const renderSection = () => {
  const utils = render(
    <ThemeProvider theme={theme}>
      <MetadataSection />
    </ThemeProvider>
  );
  const toggle = utils.container.querySelector('input[type="checkbox"]') as HTMLInputElement | null;
  return { ...utils, toggle };
};

const getFormSubmissionEnabled = () =>
  usePortalEditorStore.getState().portalData?.formSubmissionEnabled;

describe("MetadataSection — form submission toggle", () => {
  beforeEach(() => {
    // A brand-new portal seeds formSubmissionEnabled: true by default.
    usePortalEditorStore.getState().initialize();
  });

  it("defaults the Require form submission switch to on", () => {
    const { toggle } = renderSection();
    expect(toggle).not.toBeNull();
    expect(toggle!.checked).toBe(true);
    expect(getFormSubmissionEnabled()).toBe(true);
  });

  it("turns form submission off in the store when toggled off", async () => {
    const user = userEvent.setup();
    const { toggle } = renderSection();

    await user.click(toggle!);

    expect(getFormSubmissionEnabled()).toBe(false);
    expect(toggle!.checked).toBe(false);
  });

  it("reflects an existing upload-only portal (formSubmissionEnabled false)", () => {
    usePortalEditorStore.getState().initialize({ formSubmissionEnabled: false });
    const { toggle } = renderSection();
    expect(toggle).not.toBeNull();
    expect(toggle!.checked).toBe(false);
  });
});
