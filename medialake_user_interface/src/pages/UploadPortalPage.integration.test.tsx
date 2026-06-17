/**
 * MSW integration tests for the public renderer `UploadPortalPage`.
 *
 * **Validates: Requirements 7.6, 7.7, 11.3, 15.2** _(Design Properties 9 & 10)_
 *
 * These tests exercise the SurveyJS multi-page flow end-to-end through the
 * real `UploadPortalPage` (task 15.1): the access gate auto-establishes a
 * session, `GET /portal/:slug` loads a multi-page config, the shared
 * `buildSurveyJson` builds the survey, and the custom questions thread
 * `__selectedDestinationId` / `__currentPath` / metadata through `survey.data`.
 *
 *   1. Multi-page flow + single upload with metadata (Req 7.6 / 7.7 / 11.3):
 *      pass the gate, advance from the details page to the uploader page, and
 *      assert the (mocked) live uploader received the collected metadata
 *      (reserved keys excluded) plus the threaded destination + path, and that
 *      a single user Upload action fires exactly one upload.
 *   2. Session expiry mid-flow (Req 15.2): after reaching the flow, a 401 from
 *      the live uploader invokes the runtime `onSessionExpired`, which resets
 *      the page to the access gate and unmounts the survey.
 *
 * jsdom strategy / limitations
 * ----------------------------
 *   - Driving a real Uppy + AwsS3 multipart upload through jsdom is heavy and
 *     non-deterministic, so — exactly as the task 11.4 unit test does — we MOCK
 *     `@/features/portal/components/PortalUploader`. The mock records the props
 *     it receives (so we can assert `metadataFields` / `destination` /
 *     `currentPath` threaded correctly) and exposes:
 *       * an "Upload" button that calls a shared `uploadSpy` once per click,
 *         standing in for the single real Upload action (Property 10), and
 *       * an "Expire session" button that invokes `props.onSessionExpired`,
 *         standing in for a 401 surfaced by the real uploader (Req 15.2).
 *     This lets us assert "a single upload call carries the collected metadata"
 *     without a real S3 flow.
 *   - Full `<Survey>` page navigation DOES render in jsdom (ResizeObserver is
 *     polyfilled in `src/test/setup.ts`). We drive navigation via the rendered
 *     SurveyJS "Next" button and poll with `waitFor`/`findBy*` so the async
 *     auth → config-load → render → navigate pipeline stays non-flaky.
 *   - The portal API client's `baseURL` is empty in tests (no AWS config), so
 *     all `/portal/*` requests are same-origin and intercepted by MSW relative
 *     path handlers (same approach as the PortalEditor integration tests).
 */

import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { http, HttpResponse } from "msw";

import type { PortalConfig } from "@/features/portal/types/portal.types";
import { server } from "../mocks/server";

/**
 * Mock `PortalUploader` (the Uppy owner). The SurveyJS uploader question wraps
 * it; the wrapper never triggers an upload itself, so the mock is the single
 * point that would initiate one. It records the props it was rendered with and
 * exposes two buttons:
 *   - "Upload Files"   → invokes `uploadSpy(props)` exactly like one real Upload
 *                        action would (used to assert "at most once").
 *   - "Expire session" → invokes `props.onSessionExpired()` like a real 401 from
 *                        the live multipart flow (used to drive Req 15.2).
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
      <div data-testid="mock-portal-uploader">
        <button
          type="button"
          data-testid="mock-portal-uploader-upload"
          onClick={() => uploadSpy(props)}
        >
          Upload Files
        </button>
        <button
          type="button"
          data-testid="mock-portal-uploader-expire"
          onClick={() => (props.onSessionExpired as (() => void) | undefined)?.()}
        >
          Expire session
        </button>
      </div>
    );
  },
}));

// Imported AFTER the mock so the survey's uploader question picks up the mocked
// PortalUploader. Importing the page also pulls in the shared survey model +
// question renderer registration as a side effect.
import UploadPortalPage from "./UploadPortalPage";

const SLUG = "demo";
const SESSION_JWT = "test-session-jwt";

/**
 * A structurally-valid two-page config:
 *   - Page 1 "Details": a destination-selector (single destination → it
 *     auto-selects and renders no picker, threading `__selectedDestinationId`)
 *     plus a metadata-field text question ("Project code").
 *   - Page 2 "Upload": the uploader question.
 *
 * The single destination carries a `rootPath`, so the destination-selector's
 * auto-select resolves `__currentPath` to that root without a browse call.
 */
const buildConfig = (overrides: Partial<PortalConfig> = {}): PortalConfig => ({
  slug: SLUG,
  name: "Demo Portal",
  accessMode: "public",
  tokenBypassesPassphrase: false,
  isActive: true,
  structuredPathMode: false,
  captchaEnabled: false,
  metadataFields: [
    { label: "Project code", type: "text", required: false, order: 0, pageNumber: 1 },
  ],
  destinations: [
    {
      destinationId: "dest-1",
      friendlyName: "Bucket A",
      rootPath: "/incoming",
      allowBrowsing: false,
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

/**
 * Register the happy-path MSW handlers a public portal session needs:
 *   - the access gate's auto-probe (`POST /portal/:slug/auth`) returns a public
 *     session token immediately, so the gate auto-establishes a session;
 *   - `GET /portal/:slug` returns the multi-page config;
 *   - `GET /portal/:slug/browse` returns an empty listing (defensive — the
 *     rootPath auto-resolution means this is normally not hit).
 */
function useHappyPathHandlers(config: PortalConfig) {
  server.use(
    http.post("/portal/:slug/auth", () =>
      HttpResponse.json({ sessionToken: SESSION_JWT, accessMode: "public" })
    ),
    http.get("/portal/:slug", () => HttpResponse.json(config)),
    http.get("/portal/:slug/browse", () => HttpResponse.json({ prefix: "/incoming", objects: [] }))
  );
}

/** Render `<UploadPortalPage />` at `/p/:slug` inside a data router + MUI theme. */
function renderPage(slug: string = SLUG) {
  const theme = createTheme({});
  const router = createMemoryRouter([{ path: "/p/:slug", element: <UploadPortalPage /> }], {
    initialEntries: [`/p/${slug}`],
  });
  return render(
    <ThemeProvider theme={theme}>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

/**
 * Drive the shared flow up to (and including) the uploader page:
 *   1. wait for the gate to auto-authenticate and the survey to render page 1;
 *   2. fill the "Project code" metadata field;
 *   3. click the SurveyJS "Next" button to advance to the uploader page;
 *   4. wait for the mocked uploader to mount.
 */
async function advanceToUploader(user: ReturnType<typeof userEvent.setup>, projectCode: string) {
  // Page 1: the "Project code" metadata field. The destination-selector
  // auto-selected the sole destination and rendered no picker. The gate
  // auto-auth → config-load → survey-build pipeline is several async hops, so
  // allow a generous timeout for the first render to settle (non-flaky). The
  // field is queried by its accessible name because SurveyJS exposes both the
  // question wrapper and the `<input>` with the `textbox` role.
  const codeInput = await screen.findByRole(
    "textbox",
    { name: /project code/i },
    { timeout: 8000 }
  );
  await user.type(codeInput, projectCode);

  // Advance to the uploader page. The click also blurs the text field,
  // committing its value into survey.data (SurveyJS default onBlur update).
  const nextButton = await screen.findByRole("button", { name: /next/i });
  await user.click(nextButton);

  // Page 2: the mocked live uploader mounts.
  await screen.findByTestId("mock-portal-uploader-upload", {}, { timeout: 8000 });
}

beforeEach(() => {
  uploadSpy.mockClear();
  recordedProps.current = null;
});

describe("UploadPortalPage — multi-page flow + single upload (Req 7.6 / 7.7 / 11.3)", () => {
  it("threads destination/path/metadata through the survey and fires a single upload carrying the collected metadata", async () => {
    const config = buildConfig();
    useHappyPathHandlers(config);
    const user = userEvent.setup();

    renderPage();

    await advanceToUploader(user, "ABC-123");

    // The mocked live uploader received the threaded state. The path is
    // resolved asynchronously from the destination rootPath, so poll for it.
    await waitFor(() => {
      expect(recordedProps.current?.currentPath).toBe("/incoming");
    });
    const props = recordedProps.current as Record<string, unknown>;

    // Property 9 / Req 7.6: collected metadata equals the entered field value
    // with reserved keys excluded.
    expect(props.metadataFields).toEqual({ project_code: "ABC-123" });
    expect(props.metadataFields).not.toHaveProperty("__selectedDestinationId");
    expect(props.metadataFields).not.toHaveProperty("__currentPath");

    // Destination + live session threaded from survey.data + runtime context.
    expect((props.destination as { destinationId: string }).destinationId).toBe("dest-1");
    expect(props.sessionJwt).toBe(SESSION_JWT);

    // Property 10 / Req 7.7: reaching the uploader page (navigation) fires no
    // upload on its own.
    expect(uploadSpy).not.toHaveBeenCalled();

    // A single user Upload action initiates exactly one upload carrying the
    // collected metadata.
    await user.click(screen.getByTestId("mock-portal-uploader-upload"));
    expect(uploadSpy).toHaveBeenCalledTimes(1);
    expect((uploadSpy.mock.calls[0][0] as Record<string, unknown>).metadataFields).toEqual({
      project_code: "ABC-123",
    });
  }, 20000);
});

describe("UploadPortalPage — session expiry mid-flow resets to the gate (Req 15.2)", () => {
  it("resets to the access gate and unmounts the survey when the live uploader reports an expired session", async () => {
    const config = buildConfig();
    useHappyPathHandlers(config);
    const user = userEvent.setup();

    renderPage();

    await advanceToUploader(user, "XYZ-789");

    // The survey/uploader is mounted before expiry.
    expect(screen.getByTestId("mock-portal-uploader")).toBeInTheDocument();

    // After expiry the page resets to the gate, which re-probes on mount. Make
    // that re-probe require a passphrase so it does NOT silently re-authenticate
    // — this gives a deterministic, observable gate UI to assert against.
    server.use(
      http.post("/portal/:slug/auth", () =>
        HttpResponse.json({ message: "Passphrase is required" }, { status: 401 })
      )
    );

    // Simulate a 401 surfaced by the live multipart flow: the wrapper forwards
    // it to runtime.onSessionExpired, which resets accessGateState to "gate".
    await user.click(screen.getByTestId("mock-portal-uploader-expire"));

    // The access gate re-renders (passphrase prompt) and the survey is gone.
    expect(await screen.findByText(/access portal/i, {}, { timeout: 5000 })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByTestId("mock-portal-uploader")).not.toBeInTheDocument();
    });
    expect(screen.queryByTestId("mock-portal-uploader-upload")).not.toBeInTheDocument();
  }, 20000);
});
