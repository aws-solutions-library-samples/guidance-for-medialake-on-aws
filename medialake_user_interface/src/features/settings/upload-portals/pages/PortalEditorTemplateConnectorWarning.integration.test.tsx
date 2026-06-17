/**
 * Integration test for the create-from-template missing-connector warning.
 *
 * **Validates: Requirements 17.8**
 *
 * Coverage:
 *   1. Warning path — landing on `/settings/upload-portals/new?template=<id>`
 *      seeds the editor from a Template whose destination references a
 *      `connectorId` NOT present in the current connector list. After the
 *      template + connectors queries resolve, a non-blocking warning Alert
 *      appears naming the affected destination.
 *   2. No-warning path — when every seeded destination's `connectorId` is
 *      present in the connector list, no warning Alert renders.
 *   3. Snapshot semantics unchanged — after the warning fires, the seeded
 *      destinations in the store still carry their ORIGINAL `connectorId`
 *      (the warning is informational and never mutates the snapshot —
 *      Property 11).
 *
 * Strategy notes:
 *   - Mirrors `PortalEditorCreate.integration.test.tsx`: `createMemoryRouter`
 *     + `RouterProvider` (required by `useBlocker`), `QueryClientProvider`,
 *     and a stubbed sidebar so heavy subtrees stay out of the render tree.
 *   - `useErrorModal` is mocked so query error side effects can't interfere.
 *   - MSW intercepts the template GET (`/settings/portal-templates/:id`) and
 *     the connectors GET (`/connectors`). The warning logic itself is also
 *     unit-tested in `utils/findMissingConnectorDestinations.test.ts`; this
 *     test exercises the wiring + UX end to end.
 */

import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";

import type { ConnectorResponse, PortalDestination, PortalTemplate } from "@/api/types/api.types";
import { server } from "../../../../mocks/server";
import { usePortalEditorStore } from "../stores/usePortalEditorStore";

// Keep the sidebar out of the render tree.
vi.mock("../components/editor/PortalEditorSidebar", () => ({
  __esModule: true,
  default: () => <div data-testid="sidebar-stub">sidebar</div>,
  PortalEditorSidebar: () => <div data-testid="sidebar-stub">sidebar</div>,
}));

// Silence `useErrorModal`.
vi.mock("@/hooks/useErrorModal", () => ({
  useErrorModal: () => ({
    showError: vi.fn(),
  }),
}));

import PortalEditorPage from "./PortalEditorPage";

const FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJleHAiOjk5OTk5OTk5OTl9." + "sig";

const TEMPLATE_ID = "tpl-connector-warning";
const ORPHAN_CONNECTOR_ID = "connector-from-other-env";
const PRESENT_CONNECTOR_ID = "connector-here";

/** A seeded destination referencing a connector that won't exist locally. */
const ORPHAN_DESTINATION: PortalDestination = {
  destinationId: "dest-orphan",
  friendlyName: "Archive Bucket",
  connectorId: ORPHAN_CONNECTOR_ID,
  rootPath: "/archive",
  allowBrowsing: false,
  allowFolderCreation: false,
  order: 0,
  pageNumber: 1,
};

const makeTemplate = (destinations: PortalDestination[]): PortalTemplate => ({
  templateId: TEMPLATE_ID,
  name: "Connector warning template",
  pages: [
    {
      pageNumber: 1,
      title: "Upload",
      elements: [{ kind: "uploader" }],
    },
  ],
  metadataFields: [],
  destinations,
  accessMode: "public",
});

const makeConnector = (id: string): ConnectorResponse => ({
  id,
  name: `Connector ${id}`,
  type: "s3",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  storageIdentifier: "bucket",
  sqsArn: "arn:aws:sqs:us-east-1:000000000000:q",
  region: "us-east-1",
});

/**
 * Register MSW handlers for the template GET and connectors GET used by the
 * create-from-template flow.
 */
const stubHandlers = (template: PortalTemplate, connectors: ConnectorResponse[]) => {
  server.use(
    http.get("/settings/portal-templates/:id", ({ params }) => {
      expect(params.id).toBe(TEMPLATE_ID);
      return HttpResponse.json({ success: true, data: template });
    }),
    http.get("/connectors", () => {
      return HttpResponse.json({
        status: "200",
        message: "ok",
        data: { connectors },
      });
    })
  );
};

const makeQueryClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

/** Render the editor on `/settings/upload-portals/new?template=<id>`. */
const renderPage = () => {
  const queryClient = makeQueryClient();
  const theme = createTheme({});
  const router = createMemoryRouter(
    [
      {
        path: "/settings/upload-portals/new",
        element: <PortalEditorPage />,
      },
    ],
    { initialEntries: [`/settings/upload-portals/new?template=${TEMPLATE_ID}`] }
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>
  );
};

describe("PortalEditorPage create-from-template missing-connector warning (integration)", () => {
  beforeEach(() => {
    usePortalEditorStore.getState().reset();
    localStorage.setItem("medialake-auth-token", FAKE_JWT);
  });

  it("warns and names the destination when its connectorId is absent from the connector list", async () => {
    stubHandlers(makeTemplate([ORPHAN_DESTINATION]), [makeConnector(PRESENT_CONNECTOR_ID)]);

    renderPage();

    // The non-blocking warning appears once both queries resolve and naming
    // the affected destination by its friendly name. A generous timeout keeps
    // this deterministic under full-suite parallel load (the template +
    // connectors query chain can exceed the default 1000ms findBy window).
    const alert = await screen.findByRole("alert", {}, { timeout: 5000 });
    expect(alert).toHaveTextContent(/Archive Bucket/);
    expect(alert).toHaveTextContent(/[Rr]eselect a connector/);

    // Snapshot semantics unchanged (Property 11): the seeded destination still
    // carries its ORIGINAL connectorId — the warning never mutated it.
    const seeded = usePortalEditorStore.getState().portalData?.destinations as PortalDestination[];
    expect(seeded).toHaveLength(1);
    expect(seeded[0].connectorId).toBe(ORPHAN_CONNECTOR_ID);
    expect(seeded[0].friendlyName).toBe("Archive Bucket");
  });

  it("does not warn when every seeded destination's connectorId is present", async () => {
    const presentDestination: PortalDestination = {
      ...ORPHAN_DESTINATION,
      connectorId: PRESENT_CONNECTOR_ID,
    };
    stubHandlers(makeTemplate([presentDestination]), [makeConnector(PRESENT_CONNECTOR_ID)]);

    renderPage();

    // Wait until seeding has completed (store initialized with the template's
    // destination) so we're asserting the post-resolution state.
    await waitFor(
      () => {
        const seeded = usePortalEditorStore.getState().portalData?.destinations as
          | PortalDestination[]
          | undefined;
        expect(seeded?.[0]?.connectorId).toBe(PRESENT_CONNECTOR_ID);
      },
      { timeout: 5000 }
    );

    // No warning Alert renders. (The restored-draft Alert uses role="status",
    // not "alert", and is not present on a fresh create anyway.)
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
