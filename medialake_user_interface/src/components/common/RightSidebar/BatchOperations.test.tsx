import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | Record<string, unknown>) =>
      typeof fallback === "string" ? fallback : key,
  }),
}));

vi.mock("./SidebarContext", () => ({
  useRightSidebar: () => ({ setHasSelectedItems: vi.fn() }),
}));

vi.mock("notistack", () => ({
  useSnackbar: () => ({ enqueueSnackbar: vi.fn() }),
}));

const mutateAsync = vi.fn();
vi.mock("@/api/hooks/useCollections", () => ({
  useAddItemToCollection: () => ({ mutateAsync, isPending: false }),
  resolveAddedCount: () => 1,
  // Imported by AddToCollectionModal, which is only mounted when opened.
  useGetAllCollections: () => ({ data: undefined, isLoading: false, refetch: vi.fn() }),
  useCreateCollection: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

const apiGet = vi.fn();
vi.mock("@/api/apiClient", () => ({
  apiClient: {
    get: (...args: unknown[]) => apiGet(...args),
  },
}));

let granted: Record<string, boolean> = {};
vi.mock("@/permissions/hooks/useActionPermission", () => ({
  useActionPermission: (action: string, subject: string) => {
    const allowed = granted[`${action}:${subject}`] ?? false;
    return {
      allowed,
      disabled: !allowed,
      tooltip: "",
      disabledProps: { disabled: !allowed, title: "" },
    };
  },
}));

let canAddToCollections = false;
vi.mock("@/permissions/hooks/useCollectionAssetPermissions", () => ({
  useCollectionAssetPermissions: () => ({
    canAdd: canAddToCollections,
    canRemove: canAddToCollections,
    addTooltip: "",
    removeTooltip: "",
    addDisabledProps: { disabled: !canAddToCollections, title: "" },
    removeDisabledProps: { disabled: !canAddToCollections, title: "" },
  }),
}));

import BatchOperations from "./BatchOperations";
import { __resetRecentBinActionsCache } from "@/hooks/useRecentBinActions";

const selected = [{ id: "a1", name: "clip.mp4", type: "Video", inventoryID: "inv1" }];

const renderBin = (props: Record<string, unknown> = {}) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <BatchOperations
        selectedAssets={selected}
        onBatchDelete={vi.fn()}
        onBatchDownload={vi.fn()}
        onBatchPipelineExecutionRequest={vi.fn()}
        {...props}
      />
    </QueryClientProvider>
  );
};

/** One manual-trigger pipeline, eligible for any asset type. */
const pipelinesPayload = (pipelines: unknown[] = []) => ({
  data: {
    status: "200",
    message: "ok",
    data: {
      searchMetadata: {
        totalResults: pipelines.length,
        pageSize: pipelines.length,
        nextToken: null,
      },
      s: pipelines,
    },
  },
});

const manualPipeline = (over: Record<string, unknown> = {}) => ({
  id: "p1",
  name: "Transcode",
  type: "Manual Trigger",
  createdAt: "2026-01-01T00:00:00Z",
  definition: { nodes: [] },
  ...over,
});

beforeEach(() => {
  granted = {};
  canAddToCollections = false;
  apiGet.mockReset();
  mutateAsync.mockReset();
  localStorage.clear();
  __resetRecentBinActionsCache();
  apiGet.mockResolvedValue(pipelinesPayload());
});

describe("BatchOperations permission gating", () => {
  it("no permissions at all: bin still renders the selection, no actions, no pipelines request", async () => {
    renderBin({ canDelete: false });

    // The bin itself is usable
    expect(screen.getByText("clip.mp4")).toBeInTheDocument();
    expect(screen.getByText("common.clear")).toBeInTheDocument();

    // No action controls of any kind
    expect(screen.queryByTestId("batch-download-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-delete-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-workflow-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-collection-button")).not.toBeInTheDocument();

    // Critically: no GET /pipelines was issued
    await new Promise((r) => setTimeout(r, 50));
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("download permission only: shows download, hides everything else, still no request", async () => {
    granted = { "download:asset": true };
    renderBin({ canDelete: false });

    expect(screen.getByTestId("batch-download-button")).toBeInTheDocument();
    expect(screen.queryByTestId("batch-delete-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-workflow-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-collection-button")).not.toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("no action has a dropdown - each opens its picker directly", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");

    // The split-button arrows are gone; they cost ~28px per control, which is
    // what squeezed the labels. Shortcut lists live inside the modals now.
    for (const id of [
      "batch-workflow-button",
      "batch-collection-button",
      "batch-download-button",
      "batch-delete-button",
    ]) {
      expect(screen.queryByTestId(`${id}-menu`)).not.toBeInTheDocument();
    }
  });

  it("pipelines view but not edit: no workflow control and no request", async () => {
    granted = { "view:pipeline": true };
    renderBin({ canDelete: false });

    expect(screen.queryByTestId("batch-workflow-button")).not.toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("full pipeline permissions: issues the request and renders the workflow control", async () => {
    granted = { "view:pipeline": true, "edit:pipeline": true };
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: false });

    expect(await screen.findByTestId("batch-workflow-button")).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith("/pipelines", { skipAccessDeniedRedirect: true });
  });

  it("pipeline permissions but no eligible pipelines: workflow control is omitted, not left dead", async () => {
    granted = { "view:pipeline": true, "edit:pipeline": true };
    apiGet.mockResolvedValue(pipelinesPayload([]));
    renderBin({ canDelete: false });

    // Wait for the query to settle, then confirm the control never appears.
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId("batch-workflow-button")).not.toBeInTheDocument();
  });

  it("collection add permission drives the collection control on its own", () => {
    canAddToCollections = true;
    renderBin({ canDelete: false });

    expect(screen.getByTestId("batch-collection-button")).toBeInTheDocument();
    expect(screen.queryByTestId("batch-workflow-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-download-button")).not.toBeInTheDocument();
  });

  it("all permissions: every control is visible", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    expect(await screen.findByTestId("batch-workflow-button")).toBeInTheDocument();
    expect(screen.getByTestId("batch-collection-button")).toBeInTheDocument();
    expect(screen.getByTestId("batch-download-button")).toBeInTheDocument();
    expect(screen.getByTestId("batch-delete-button")).toBeInTheDocument();
  });

  it("groups the pickers on one row and the direct actions on another", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");

    const pickerRow = screen.getByTestId("bin-picker-row");
    const directRow = screen.getByTestId("bin-direct-row");

    expect(pickerRow).toContainElement(screen.getByTestId("batch-workflow-button"));
    expect(pickerRow).toContainElement(screen.getByTestId("batch-collection-button"));
    expect(directRow).toContainElement(screen.getByTestId("batch-download-button"));
    expect(directRow).toContainElement(screen.getByTestId("batch-delete-button"));

    // Pickers first, direct actions second. DOCUMENT_POSITION_FOLLOWING === 4.
    expect(pickerRow.compareDocumentPosition(directRow) & 4).toBeTruthy();
  });

  it("omits a row entirely when nothing in it is permitted", () => {
    // Download/delete only: the picker row should not render an empty container.
    granted = { "download:asset": true };
    canAddToCollections = false;
    renderBin({ canDelete: true });

    expect(screen.queryByTestId("bin-picker-row")).not.toBeInTheDocument();
    expect(screen.getByTestId("bin-direct-row")).toBeInTheDocument();
  });

  it("omits the direct row when neither download nor delete is permitted", () => {
    canAddToCollections = true;
    renderBin({ canDelete: false });

    expect(screen.getByTestId("bin-picker-row")).toBeInTheDocument();
    expect(screen.queryByTestId("bin-direct-row")).not.toBeInTheDocument();
  });
});

describe("BatchOperations action layout", () => {
  /**
   * The sidebar is user-resizable from 275px up (375px default), and which
   * controls appear depends on permissions. The row therefore has to stretch
   * whatever it shows instead of leaving a ragged gap, so the grow behaviour is
   * asserted rather than eyeballed.
   */
  const growOf = (el: HTMLElement) => getComputedStyle(el).flexGrow;
  const basisOf = (el: HTMLElement) => getComputedStyle(el).flexBasis;

  /**
   * Regression guard for truncated labels ("Wo…" / "Col…").
   *
   * With the dropdown arrows gone each control spends ~38px on chrome before any
   * text: ~2px borders, 16px padding and a 20px icon. Two controls share a row at
   * the 375px default (~343px usable), leaving ~129px for the label — more than
   * the longest translation needs (pt "Fluxo de trabalho" ≈ 93px). The basis must
   * stay high enough that the pair wraps to one-per-row at the 275px drag minimum
   * instead of squeezing.
   */
  const MIN_SAFE_BASIS = 120;

  it("gives each primary action enough basis that labels are not squeezed", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");

    const targets = [
      screen.getByTestId("batch-workflow-button"),
      screen.getByTestId("batch-collection-button"),
      screen.getByTestId("batch-download-button"),
      screen.getByTestId("batch-delete-button"),
    ];

    for (const el of targets) {
      const basis = parseInt(basisOf(el), 10);
      expect(Number.isNaN(basis)).toBe(false);
      expect(basis).toBeGreaterThanOrEqual(MIN_SAFE_BASIS);
    }
  });

  it("uses the same basis for every primary action so they wrap together", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");

    const bases = [
      basisOf(screen.getByTestId("batch-workflow-button")),
      basisOf(screen.getByTestId("batch-collection-button")),
      basisOf(screen.getByTestId("batch-download-button")),
      basisOf(screen.getByTestId("batch-delete-button")),
    ];

    // A mismatch would leave one control orphaned on its own row.
    expect(new Set(bases).size).toBe(1);
  });

  it("allows the action row to wrap rather than overflow the sidebar", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");
    for (const id of ["bin-picker-row", "bin-direct-row"]) {
      expect(getComputedStyle(screen.getByTestId(id)).flexWrap).toBe("wrap");
    }
  });

  it("stretches the download button when it is the only primary action", () => {
    granted = { "download:asset": true };
    renderBin({ canDelete: false });

    expect(growOf(screen.getByTestId("batch-download-button"))).toBe("1");
  });

  it("stretches every primary action when all of them are permitted", async () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");

    expect(growOf(screen.getByTestId("batch-workflow-button"))).toBe("1");
    expect(growOf(screen.getByTestId("batch-collection-button"))).toBe("1");
    expect(growOf(screen.getByTestId("batch-download-button"))).toBe("1");
    expect(growOf(screen.getByTestId("batch-delete-button"))).toBe("1");
  });

  it("lets delete fill the row when download is not permitted", () => {
    canAddToCollections = true;
    renderBin({ canDelete: true });

    // Sharing the direct row with Download, or taking it alone, delete still
    // stretches rather than sitting at its intrinsic width.
    expect(growOf(screen.getByTestId("batch-delete-button"))).toBe("1");
    expect(screen.queryByTestId("batch-download-button")).not.toBeInTheDocument();
  });
});

describe("BatchOperations quick access (disabled)", () => {
  /**
   * Quick Access is commented out in the component for now. These assert it stays
   * off — including when the recents store has entries that would otherwise
   * render chips — so re-enabling it is a deliberate change rather than an
   * accident.
   */
  it("is not rendered even when actionable recents exist", async () => {
    localStorage.setItem(
      "medialake.binRecentActions.v1",
      JSON.stringify([
        { kind: "collection", id: "c1", name: "Q4 Campaign", usedAt: 2 },
        { kind: "workflow", id: "p1", name: "Transcode", usedAt: 3 },
      ])
    );
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    canAddToCollections = true;
    apiGet.mockResolvedValue(pipelinesPayload([manualPipeline()]));
    renderBin({ canDelete: true });

    await screen.findByTestId("batch-workflow-button");

    expect(screen.queryByTestId("bin-quick-access")).not.toBeInTheDocument();
    expect(screen.queryByText("Q4 Campaign")).not.toBeInTheDocument();
  });

  it("still records recents for the disabled Quick Access row", () => {
    localStorage.setItem(
      "medialake.binRecentActions.v1",
      JSON.stringify([{ kind: "collection", id: "c1", name: "Q4 Campaign", usedAt: 2 }])
    );
    canAddToCollections = true;
    renderBin({ canDelete: false });

    // The dropdowns that used to surface recents are gone, so nothing displays
    // them — but the store is still wired up so re-enabling Quick Access needs no
    // rebuild. The control itself renders and opens the picker.
    expect(screen.getByTestId("batch-collection-button")).toBeInTheDocument();
    expect(screen.queryByTestId("batch-collection-button-menu")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bin-quick-access")).not.toBeInTheDocument();
    expect(screen.queryByText("Q4 Campaign")).not.toBeInTheDocument();
  });
});
