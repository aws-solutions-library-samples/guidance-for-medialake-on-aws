/**
 * Integration tests for PortalEditorPage.
 *
 * **Validates: Requirements 1.1, 3.1**
 *
 * Coverage:
 *   1. Navigating to `/settings/upload-portals/:id/edit` triggers
 *      `useGetPortal`, which hits an MSW-mocked `GET /settings/portals/:id`.
 *      Once the portal arrives, `store.initialize(portal)` runs so the
 *      sidebar + preview see the hydrated appearance
 *      (Requirement 1.1 — "portal data pre-loaded via `useGetPortal(id)`").
 *   2. The toolbar breadcrumb renders with the portal's name once data
 *      has loaded (stand-in for a visible "we got past the loading
 *      spinner" signal).
 *   3. After initialization `usePortalEditorStore.getState().isInitialized`
 *      is `true` — asserting the store-side postcondition of the data
 *      flow independently of any specific DOM assertion.
 *   4. The preview region mounts (Requirement 3.1 — every edit reflects
 *      in the preview, so the preview must be present in the DOM).
 *   5. The toolbar mounts with the documented `role="toolbar"`.
 *
 * Strategy notes:
 *   - We mock `PortalEditorSidebar` with a lightweight stub so Tiptap
 *     (inside `ContentSection` etc.) does not initialize during the
 *     integration test. The sidebar's rendering is covered by unit tests
 *     on each section component.
 *   - We mock the `@/hooks/useErrorModal` hook so `useGetPortal` does not
 *     try to surface an error modal when fetches succeed (it still
 *     imports cleanly, the `showError` spy just never fires on the happy
 *     path tested here).
 *   - A fake JWT is seeded into `localStorage` under the auth-token key
 *     so the apiClient's request interceptor does not throw
 *     "No authentication token available" on the outbound request.
 */

import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";

import type { Portal } from "@/api/types/api.types";
import { server } from "../../../../mocks/server";
import { usePortalEditorStore } from "../stores/usePortalEditorStore";

// Mock the sidebar so heavy subtrees (Tiptap, color pickers) don't mount
// during the integration test. The sidebar gets its own coverage in
// PortalEditorSidebar + per-section unit tests.
vi.mock("../components/editor/PortalEditorSidebar", () => ({
  __esModule: true,
  default: () => <div data-testid="sidebar-stub">sidebar</div>,
  PortalEditorSidebar: () => <div data-testid="sidebar-stub">sidebar</div>,
}));

// `useErrorModal` pulls in the real ErrorProvider, which is unnecessary for
// this test. Stubbing it keeps the render tree minimal.
vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({
    showError: vi.fn(),
  }),
}));

import PortalEditorPage from "./PortalEditorPage";

/**
 * A syntactically valid, non-expired JWT used to satisfy the apiClient's
 * auth interceptor. `exp` is far in the future so
 * `isTokenExpiringSoon` returns `false` and no refresh is attempted.
 */
const FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJleHAiOjk5OTk5OTk5OTl9." + "sig";

const TEST_PORTAL_ID = "test-portal-id";

/**
 * Minimal `Portal` fixture returned by the MSW handler.
 *
 * Includes only the fields the editor exercises during mount; unspecified
 * fields are omitted and the store's `initialize` deep-merges defaults for
 * the `appearance` slice.
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
  metadataFields: [{ label: "Your Name", type: "text", required: true, order: 0 }],
  destinations: [
    {
      destinationId: "dest-1",
      friendlyName: "Project Assets",
      connectorId: "connector-1",
      rootPath: "/project",
      allowBrowsing: false,
      allowFolderCreation: false,
      order: 0,
    },
  ],
  pages: [],
  captchaEnabled: false,
  formSubmissionEnabled: true,
  createdBy: "test-user",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
});

/**
 * Fresh QueryClient per test with retries disabled so assertions about
 * loading/error states are deterministic.
 */
const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

/**
 * Render `<PortalEditorPage />` at `/settings/upload-portals/:id/edit`
 * wrapped in the providers it depends on: data router
 * (`createMemoryRouter` + `RouterProvider`, required because
 * `PortalEditorPage` uses `useBlocker`), QueryClient, MUI ThemeProvider.
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

describe("PortalEditorPage (integration)", () => {
  beforeEach(() => {
    // Reset the singleton editor store so state from a previous test
    // cannot bleed in (e.g. `isInitialized` leftover from an earlier
    // render path).
    usePortalEditorStore.getState().reset();

    // Seed the JWT so the apiClient's outbound request does not throw
    // "No authentication token available" in the request interceptor.
    localStorage.setItem("medialake-auth-token", FAKE_JWT);
  });

  it("loads an existing portal, initializes the store, and mounts the preview", async () => {
    const portal = makePortalFixture();

    // MSW matches against same-origin URLs. In jsdom the origin is
    // `http://localhost:3000` by default and the apiClient's baseURL is
    // empty (no AWS config in tests), so `useGetPortal("test-portal-id")`
    // issues a same-origin request to `/settings/portals/test-portal-id`
    // which this handler intercepts.
    server.use(
      http.get("/settings/portals/:id", ({ params }) => {
        expect(params.id).toBe(TEST_PORTAL_ID);
        // `apiClient` unwraps Lambda-proxy `{statusCode, body}` shapes,
        // but the portals endpoints return the bare `ApiResponse` shape
        // — so we return `{ success, data }` directly here.
        return HttpResponse.json({ success: true, data: portal });
      })
    );

    renderPage();

    // The toolbar is present immediately (it renders outside the
    // loading fallback).
    expect(screen.getByRole("toolbar", { name: "Editor actions" })).toBeInTheDocument();

    // Wait for the portal name to appear in the toolbar breadcrumb — the
    // observable signal that (a) the fetch resolved and (b) the store
    // initialized with the portal payload. Scoping the query to the
    // toolbar avoids colliding with the preview mock which also renders
    // the portal name inside its mock header. A generous timeout keeps
    // this resilient when the full suite runs in parallel and the MSW +
    // React Query + store-init chain competes for the event loop (the
    // default 1000ms window can be exceeded under heavy load).
    await waitFor(
      () => {
        const toolbar = screen.getByRole("toolbar", {
          name: "Editor actions",
        });
        expect(within(toolbar).getByText("My Test Portal")).toBeInTheDocument();
      },
      { timeout: 5000 }
    );

    // Store-side postcondition: `initialize(portal)` ran.
    expect(usePortalEditorStore.getState().isInitialized).toBe(true);

    // The preview region mounts (Requirement 3.1 — preview must be
    // wired so appearance changes can reflect).
    expect(screen.getByRole("region", { name: "Portal preview" })).toBeInTheDocument();
  }, 15000);
});
