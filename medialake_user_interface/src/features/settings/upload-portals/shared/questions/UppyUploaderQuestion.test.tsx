import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material";

import { Model } from "survey-core";
import type { Question } from "survey-core";

import type { PortalConfig } from "@/features/portal/types/portal.types";

import { buildSurveyJson } from "../portalSurveyModel";
import {
  CURRENT_PATH_KEY,
  PortalRuntimeContext,
  SELECTED_DESTINATION_KEY,
  type PortalRuntimeValue,
} from "../PortalRuntimeContext";

/**
 * Tests for the custom `portal-uppy-uploader` SurveyJS question renderer.
 *
 * **Validates: Requirements 7.6, 7.7, 15.1** _(Design Properties 9 & 10)_
 *
 *  - Property 10 / Req 7.7: a single Upload action triggers the Uppy upload at
 *    most once and page navigation (re-render / re-mount) fires no extra upload.
 *    The wrapper never initiates an upload itself — `PortalUploader` owns the
 *    single Upload action — so we mock `PortalUploader` and count how many
 *    times it would initiate an upload across renders + simulated navigation.
 *  - Property 9 / Req 7.6: the live uploader receives `metadataFields` equal to
 *    the collected metadata-field values with the reserved keys excluded.
 *  - Req 15.1: reaching the uploader with an empty `__selectedDestinationId`
 *    renders the no-destination warning and the required uploader question
 *    stays unanswered, so survey completion is blocked.
 */

/**
 * Mock `PortalUploader` (the Uppy owner). The wrapper under test must NOT call
 * any upload trigger itself; `PortalUploader` exposes a single Upload action.
 * The mock records the props it was rendered with and exposes a button that,
 * when clicked, invokes the shared `uploadSpy` exactly the way a real Upload
 * action would — letting us assert "at most once per Upload action".
 */
const { uploadSpy, recordedProps } = vi.hoisted(() => ({
  uploadSpy: vi.fn(),
  recordedProps: { current: null as Record<string, unknown> | null },
}));

vi.mock("@/features/portal/components/PortalUploader", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    recordedProps.current = props;
    return (
      <button
        type="button"
        data-testid="mock-portal-uploader-upload"
        onClick={() => uploadSpy(props)}
      >
        Upload Files
      </button>
    );
  },
}));

// Imported AFTER the mock is declared so the renderer picks up the mocked
// PortalUploader. Importing also registers the custom question models/renderer.
import { UppyUploaderRenderer } from "./UppyUploaderQuestion";

const theme = createTheme();

/** A structurally-valid single-destination config with an uploader page. */
const buildConfig = (overrides: Partial<PortalConfig> = {}): PortalConfig => ({
  slug: "demo",
  name: "Demo Portal",
  accessMode: "public",
  tokenBypassesPassphrase: false,
  isActive: true,
  structuredPathMode: false,
  captchaEnabled: false,
  metadataFields: [
    { label: "Project code", type: "text", required: true, order: 0, pageNumber: 1 },
  ],
  destinations: [
    {
      destinationId: "dest-1",
      friendlyName: "Bucket A",
      allowBrowsing: true,
      allowFolderCreation: false,
      order: 0,
      pageNumber: 1,
    },
  ],
  pages: [
    {
      pageNumber: 1,
      title: "Details",
      elements: [
        { kind: "destination-selector" },
        { kind: "metadata-field", fieldKey: "project_code" },
      ],
    },
    {
      pageNumber: 2,
      title: "Upload",
      elements: [{ kind: "uploader" }],
    },
  ],
  ...overrides,
});

/** Build a real survey-core Model from a config and return it + its uploader question. */
function buildSurveyAndUploader(config: PortalConfig): {
  survey: Model;
  uploader: Question;
} {
  const survey = new Model(buildSurveyJson(config));
  const uploader = survey.getQuestionByName("__uploader") as Question;
  return { survey, uploader };
}

function renderRenderer(question: Question, runtime: PortalRuntimeValue) {
  return render(
    <ThemeProvider theme={theme}>
      <PortalRuntimeContext.Provider value={runtime}>
        <UppyUploaderRenderer question={question} />
      </PortalRuntimeContext.Provider>
    </ThemeProvider>
  );
}

const publicRuntime = (config: PortalConfig): PortalRuntimeValue => ({
  mode: "public",
  slug: config.slug,
  sessionJwt: "session-jwt",
  config,
});

beforeEach(() => {
  // The PortalUploader mock's spy and recorded props persist across renders;
  // reset them so each test asserts against a clean slate.
  uploadSpy.mockClear();
  recordedProps.current = null;
});

describe("UppyUploaderRenderer — single upload trigger (Req 7.7 / Property 10)", () => {
  it("does not initiate an upload merely by rendering or re-rendering (no nav-triggered fire)", async () => {
    const config = buildConfig();
    const { survey, uploader } = buildSurveyAndUploader(config);
    survey.setValue(SELECTED_DESTINATION_KEY, "dest-1");
    survey.setValue(CURRENT_PATH_KEY, "/incoming");

    const { rerender } = renderRenderer(uploader, publicRuntime(config));

    // Rendering the uploader page must not fire an upload on its own.
    expect(uploadSpy).not.toHaveBeenCalled();

    // Simulate navigating away and back (re-render) — still no upload.
    rerender(
      <ThemeProvider theme={theme}>
        <PortalRuntimeContext.Provider value={publicRuntime(config)}>
          <UppyUploaderRenderer question={uploader} />
        </PortalRuntimeContext.Provider>
      </ThemeProvider>
    );
    expect(uploadSpy).not.toHaveBeenCalled();

    // A single user Upload action initiates exactly one upload.
    await userEvent.click(screen.getByTestId("mock-portal-uploader-upload"));
    expect(uploadSpy).toHaveBeenCalledTimes(1);

    // Re-rendering after the action (e.g. navigation back to the page) must
    // not fire an additional upload.
    rerender(
      <ThemeProvider theme={theme}>
        <PortalRuntimeContext.Provider value={publicRuntime(config)}>
          <UppyUploaderRenderer question={uploader} />
        </PortalRuntimeContext.Provider>
      </ThemeProvider>
    );
    expect(uploadSpy).toHaveBeenCalledTimes(1);
  });

  it("passes collected metadata (reserved keys excluded) to the uploader (Req 7.6 / Property 9)", () => {
    const config = buildConfig();
    const { survey, uploader } = buildSurveyAndUploader(config);
    survey.setValue(SELECTED_DESTINATION_KEY, "dest-1");
    survey.setValue(CURRENT_PATH_KEY, "/incoming");
    survey.setValue("project_code", "ABC-123");

    renderRenderer(uploader, publicRuntime(config));

    expect(recordedProps.current).not.toBeNull();
    const props = recordedProps.current as Record<string, unknown>;
    // Only the metadata-field value flows through; reserved keys are excluded.
    expect(props.metadataFields).toEqual({ project_code: "ABC-123" });
    expect(props.metadataFields).not.toHaveProperty(SELECTED_DESTINATION_KEY);
    expect(props.metadataFields).not.toHaveProperty(CURRENT_PATH_KEY);
    // Destination/path/session are threaded from survey.data + runtime.
    expect((props.destination as { destinationId: string }).destinationId).toBe("dest-1");
    expect(props.currentPath).toBe("/incoming");
    expect(props.sessionJwt).toBe("session-jwt");
  });

  it("falls back to the default media allow-list when the portal sets no allowedFileTypes", () => {
    // Mirrors the server-side ALLOWED_CONTENT_TYPES so the uploader rejects
    // disallowed files at selection rather than failing the presigned request.
    const config = buildConfig();
    const { survey, uploader } = buildSurveyAndUploader(config);
    survey.setValue(SELECTED_DESTINATION_KEY, "dest-1");

    renderRenderer(uploader, publicRuntime(config));

    const props = recordedProps.current as Record<string, unknown>;
    expect(props.allowedFileTypes).toEqual([
      "audio/*",
      "video/*",
      "image/*",
      "application/x-mpegURL",
      "application/dash+xml",
    ]);
  });

  it("uses the portal's explicit allowedFileTypes when provided", () => {
    const config = buildConfig({ allowedFileTypes: ["image/png", "image/jpeg"] });
    const { survey, uploader } = buildSurveyAndUploader(config);
    survey.setValue(SELECTED_DESTINATION_KEY, "dest-1");

    renderRenderer(uploader, publicRuntime(config));

    const props = recordedProps.current as Record<string, unknown>;
    expect(props.allowedFileTypes).toEqual(["image/png", "image/jpeg"]);
  });
});

describe("UppyUploaderRenderer — empty destination blocks completion (Req 15.1)", () => {
  it("renders the no-destination warning when multiple destinations exist and none is selected", () => {
    // With more than one destination, the uploader cannot auto-resolve a
    // target, so an unselected destination must block the live uploader.
    const config = buildConfig({
      destinations: [
        {
          destinationId: "dest-1",
          friendlyName: "Bucket A",
          allowBrowsing: true,
          allowFolderCreation: false,
          order: 0,
          pageNumber: 1,
        },
        {
          destinationId: "dest-2",
          friendlyName: "Bucket B",
          allowBrowsing: true,
          allowFolderCreation: false,
          order: 1,
          pageNumber: 1,
        },
      ],
    });
    const { uploader } = buildSurveyAndUploader(config);

    // No destination selected → public runtime with a live session.
    renderRenderer(uploader, publicRuntime(config));

    expect(screen.getByTestId("portal-uploader-no-destination")).toBeInTheDocument();
    // The live uploader must not have rendered (no upload initiation surface).
    expect(screen.queryByTestId("mock-portal-uploader-upload")).not.toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });

  it("auto-resolves the sole destination when none is explicitly selected", () => {
    // A single-destination portal needs no destination-selector: the uploader
    // resolves the one destination so the upload surface renders.
    const config = buildConfig();
    const { uploader } = buildSurveyAndUploader(config);

    renderRenderer(uploader, publicRuntime(config));

    expect(screen.queryByTestId("portal-uploader-no-destination")).not.toBeInTheDocument();
    expect(recordedProps.current).not.toBeNull();
    const props = recordedProps.current as Record<string, unknown>;
    expect((props.destination as { destinationId: string }).destinationId).toBe("dest-1");
  });

  it("leaves the required uploader question unanswered with an empty value", () => {
    const { uploader } = buildSurveyAndUploader(buildConfig());

    // The uploader question is required and starts empty → completion blocked.
    expect(uploader.isRequired).toBe(true);
    expect(uploader.isEmpty()).toBe(true);
    expect(uploader.hasErrors()).toBe(true);
  });

  it("becomes answered once a completed-upload marker is recorded", () => {
    const { survey, uploader } = buildSurveyAndUploader(buildConfig());

    // The wrapper writes a non-empty array marker after a completed upload;
    // that flips the required question to answered so completion is unblocked.
    survey.setValue("__uploader", ["uploaded"]);

    expect(uploader.isEmpty()).toBe(false);
    expect(uploader.hasErrors()).toBe(false);
  });
});

describe("UppyUploaderRenderer — preview mode", () => {
  it("renders the mock drop-zone and never the live uploader in preview mode", () => {
    const config = buildConfig();
    const { uploader } = buildSurveyAndUploader(config);

    renderRenderer(uploader, {
      mode: "preview",
      slug: config.slug,
      sessionJwt: null,
      config,
    });

    expect(screen.getByTestId("portal-mock-uploader")).toBeInTheDocument();
    expect(screen.queryByTestId("mock-portal-uploader-upload")).not.toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });
});
