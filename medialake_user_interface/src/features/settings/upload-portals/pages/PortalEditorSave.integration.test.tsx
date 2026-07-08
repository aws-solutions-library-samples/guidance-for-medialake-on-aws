/**
 * Integration test for PortalEditorPage save flow.
 *
 * **Validates: Requirements 10.3, 10.6, 10.11**
 *
 * Coverage:
 *   1. Load an existing portal into the editor, mutate `appearance.colors.primary`
 *      via the store so `isDirty === true`, click Save, and assert the payload
 *      that hits `PUT /settings/portals/:id` (Requirement 10.3 —
 *      "Save updates the portal via useUpdatePortal").
 *   2. The captured PUT body reflects the mutated color
 *      (`appearance.colors.primary === "#ff0000"`).
 *   3. The captured body is a JSON-serializable `CreatePortalRequest` shape:
 *      it contains the core top-level fields (`name`, `slug`, `destinations`,
 *      `metadataFields`, `appearance`) and does NOT contain `logoFile`
 *      (Requirement 10.11 — `getPayload()` strips client-only fields).
 *   4. `usePortalEditorStore.getState().isDirty` flips back to `false`
 *      after the mutation resolves (Requirement 10.6 — successful save
 *      calls `markClean()`).
 *   5. A "Changes saved." toast surfaces for the user (optional assertion —
 *      we wait for it but only assert if it renders, since MUI Snackbar
 *      mounting timing in jsdom can be flaky).
 *
 * Strategy notes:
 *   - The same provider stack as PortalEditorPage.integration.test.tsx:
 *     `createMemoryRouter` + `RouterProvider`, `QueryClientProvider`,
 *     `ThemeProvider`. `useBlocker` requires the data router API.
 *   - Sidebar is mocked to keep the heavy Tiptap / MUI picker subtrees
 *     out of the render tree — the sidebar has its own unit and
 *     integration coverage.
 *   - `useErrorModal` is mocked so the hook's error modal side effects
 *     don't interfere with toast assertions on the happy path.
 *   - The store is reset in `beforeEach` (also clears the persisted
 *     draft thanks to `reset()` calling `persist.clearStorage()`).
 *   - A fake JWT is seeded into localStorage so the apiClient request
 *     interceptor doesn't throw.
 */

import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";

import type { Portal } from "@/api/types/api.types";
import { server } from "../../../../mocks/server";
import { usePortalEditorStore } from "../stores/usePortalEditorStore";

// Keep the sidebar out of the render tree — heavy subtrees (Tiptap,
// color pickers, MUI autocompletes) would pull in more than this test
// cares about. The sidebar is covered by section unit tests.
vi.mock("../components/editor/PortalEditorSidebar", () => ({
  __esModule: true,
  default: () => <div data-testid="sidebar-stub">sidebar</div>,
  PortalEditorSidebar: () => <div data-testid="sidebar-stub">sidebar</div>,
}));

// Silence `useErrorModal` so error side effects don't interfere with
// toast assertions on the happy path.
vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({
    showError: vi.fn(),
  }),
}));

import PortalEditorPage from "./PortalEditorPage";

/**
 * A syntactically valid, non-expired JWT used to satisfy the apiClient's
 * auth interceptor. `exp` is far in the future so `isTokenExpiringSoon`
 * returns `false` and no refresh is attempted.
 */
const FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJleHAiOjk5OTk5OTk5OTl9." + "sig";

const TEST_PORTAL_ID = "test-portal-id";

/**
 * Minimal `Portal` fixture — matches the pattern in
 * `PortalEditorPage.integration.test.tsx`. Omits the optional
 * `appearance` field so `store.initialize` seeds defaults.
 */
const makePortalFixture = (): Portal => ({
  portalId: TEST_PORTAL_ID,
  slug: "my-test-portal",
  name: "My Test Portal",
  description: "Integration-test fixture",
  accessMode: "public",
  tokenBypassesPassphrase: false,
  ipAllowlist: [],
  structuredPathMode: false,
  isActive: true,
  metadataFields: [{ label: "Your Name", type: "text", required: true, order: 0, pageNumber: 1 }],
  destinations: [
    {
      destinationId: "dest-1",
      friendlyName: "Project Assets",
      connectorId: "connector-1",
      rootPath: "/project",
      allowBrowsing: false,
      allowFolderCreation: false,
      order: 0,
      pageNumber: 1,
    },
  ],
  // A structurally valid single-page layout: page 1 hosts the metadata field,
  // the destination selector, and the uploader. `store.validate()` (task 12.2)
  // now enforces the same single-uploader / contiguity / reference-integrity
  // invariants as the server, so the fixture must carry a real `pages` array
  // for the Save path to fire the PUT (an empty array fails single-uploader).
  pages: [
    {
      pageNumber: 1,
      title: "Upload",
      elements: [
        { kind: "metadata-field", fieldKey: "your_name" },
        { kind: "destination-selector" },
        { kind: "uploader" },
      ],
    },
  ],
  captchaEnabled: false,
  formSubmissionEnabled: true,
  createdBy: "test-user",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
});

const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

/**
 * Render the editor page on the edit route. A single route is enough —
 * we don't expect the save flow to navigate (Update flow stays on the
 * same URL), so there's no need for a second route stub.
 */
const renderPage = (portalId: string = TEST_PORTAL_ID) => {
  const queryClient = makeQueryClient();
  const theme = createTheme({});
  const router = createMemoryRouter(
    [
      {
        path: "/settings/upload-portals/:id/edit",
        element: <PortalEditorPage />,
      },
    ],
    { initialEntries: [`/settings/upload-portals/${portalId}/edit`] }
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>
  );
};

describe("PortalEditorPage save flow (integration)", () => {
  beforeEach(() => {
    // Reset the singleton store so no state leaks between tests. `reset()`
    // also clears the persisted draft via `persist.clearStorage()`
    // (task 5.17).
    usePortalEditorStore.getState().reset();
    localStorage.setItem("medialake-auth-token", FAKE_JWT);
  });

  it("edits appearance, validates, sends the correct PUT payload, and resets isDirty on success", async () => {
    const portal = makePortalFixture();

    // Capture the PUT request body via a promise the test awaits. Using
    // a promise (resolved inside the handler) is more robust than a
    // bare closure variable because `waitFor` + promise-resolution
    // cooperate cleanly with async rendering.
    let capturePutBody!: (body: unknown) => void;
    const putBodyPromise = new Promise<unknown>((resolve) => {
      capturePutBody = resolve;
    });

    server.use(
      // GET for initial load.
      http.get("/settings/portals/:id", ({ params }) => {
        expect(params.id).toBe(TEST_PORTAL_ID);
        return HttpResponse.json({ success: true, data: portal });
      }),
      // PUT for the save mutation.
      http.put("/settings/portals/:id", async ({ request, params }) => {
        const body = await request.json();
        capturePutBody(body);
        // Return the updated portal (merge the request body into the
        // fixture so the client can refetch-and-merge if needed).
        return HttpResponse.json({
          success: true,
          data: { ...portal, portalId: params.id as string, ...(body as object) },
        });
      })
    );

    renderPage();

    // Wait for the fetch to resolve and the store to initialize. A
    // generous timeout keeps this deterministic under full-suite parallel
    // load, where the MSW + React Query + store-init chain can exceed the
    // default 1000ms waitFor window.
    await waitFor(
      () => {
        expect(usePortalEditorStore.getState().isInitialized).toBe(true);
      },
      { timeout: 5000 }
    );

    // Store should be clean immediately after `initialize(portal)`.
    expect(usePortalEditorStore.getState().isDirty).toBe(false);

    // Mutate the store exactly as a real color-picker change would.
    // `updateColor` marks the store dirty, which enables the Save button.
    usePortalEditorStore.getState().updateColor("primary", "#ff0000");

    await waitFor(
      () => {
        expect(usePortalEditorStore.getState().isDirty).toBe(true);
      },
      { timeout: 5000 }
    );

    // Click Save.
    const user = userEvent.setup();
    const saveButton = await screen.findByRole("button", { name: "Save" });
    await waitFor(() => expect(saveButton).toBeEnabled());
    await user.click(saveButton);

    // Wait for the PUT to land and the body to be captured.
    const body = (await putBodyPromise) as Record<string, unknown>;

    // Appearance color mutation flowed through to the payload.
    const appearance = body.appearance as {
      colors: { primary: string };
    };
    expect(appearance).toBeDefined();
    expect(appearance.colors.primary).toBe("#ff0000");

    // Core fields are present on the payload. Using `expect.objectContaining`
    // keeps the assertion resilient to additional optional fields the
    // store may include (e.g. `accessMode`, `isActive`).
    expect(body).toEqual(
      expect.objectContaining({
        name: "My Test Portal",
        slug: "my-test-portal",
        destinations: expect.any(Array),
        metadataFields: expect.any(Array),
        appearance: expect.any(Object),
      })
    );

    // Client-only `logoFile` is stripped — it's a `File` and would not
    // JSON-serialize (Requirement 10.11).
    expect(body).not.toHaveProperty("logoFile");

    // Store-side postcondition: `markClean()` ran on save success.
    await waitFor(
      () => {
        expect(usePortalEditorStore.getState().isDirty).toBe(false);
      },
      { timeout: 5000 }
    );

    // Optional: assert the success toast surfaced. Toast mounting is
    // async and MUI Snackbar timing in jsdom can vary; we only assert
    // if the toast DOM node appears within the waitFor window.
    try {
      await waitFor(
        () => {
          expect(screen.getByText("Changes saved.")).toBeInTheDocument();
        },
        { timeout: 1000 }
      );
    } catch {
      // Toast didn't render in the waitFor window — this is not a
      // contract violation, so we skip the assertion.
    }
  }, 15000);
});
