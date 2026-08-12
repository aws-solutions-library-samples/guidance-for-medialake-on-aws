import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string, fallback?: string) => fallback ?? key }),
}));

vi.mock("./SidebarContext", () => ({
  useRightSidebar: () => ({ setHasSelectedItems: vi.fn() }),
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

import BatchOperations from "./BatchOperations";

const selected = [{ id: "a1", name: "clip.mp4", type: "Video" }];

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

beforeEach(() => {
  granted = {};
  apiGet.mockReset();
  apiGet.mockResolvedValue({
    data: {
      status: "200",
      message: "ok",
      data: { searchMetadata: { totalResults: 0, pageSize: 0, nextToken: null }, s: [] },
    },
  });
});

describe("BatchOperations permission gating", () => {
  it("no permissions at all: bin still renders the selection, no actions, no pipelines request", async () => {
    renderBin({ canDelete: false });

    // The bin itself is usable
    expect(screen.getByText("clip.mp4")).toBeInTheDocument();
    expect(screen.getByText("common.clear")).toBeInTheDocument();

    // No action buttons
    expect(screen.queryByTestId("batch-download-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("batch-delete-button")).not.toBeInTheDocument();
    expect(screen.queryByText("common.batchOperations.runPipeline")).not.toBeInTheDocument();

    // Critically: no GET /pipelines was issued
    await new Promise((r) => setTimeout(r, 50));
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("download permission only: shows download, hides delete + pipelines, still no request", async () => {
    granted = { "download:asset": true };
    renderBin({ canDelete: false });

    expect(screen.getByTestId("batch-download-button")).toBeInTheDocument();
    expect(screen.queryByTestId("batch-delete-button")).not.toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("pipelines view but not edit: no pipeline UI and no request", async () => {
    granted = { "view:pipeline": true };
    renderBin({ canDelete: false });

    expect(screen.queryByText("common.batchOperations.runPipeline")).not.toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("full pipeline permissions: issues the request and renders the pipeline row", async () => {
    granted = { "view:pipeline": true, "edit:pipeline": true };
    renderBin({ canDelete: true });

    // Loading state renders the pipeline row immediately
    expect(await screen.findByText("common.batchOperations.runPipeline")).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith("/pipelines", { skipAccessDeniedRedirect: true });
  });

  it("all permissions: both action icons visible", () => {
    granted = { "download:asset": true, "view:pipeline": true, "edit:pipeline": true };
    renderBin({ canDelete: true });

    expect(screen.getByTestId("batch-download-button")).toBeInTheDocument();
    expect(screen.getByTestId("batch-delete-button")).toBeInTheDocument();
  });

  it("header keeps a stable height with and without action icons", () => {
    granted = {};
    const { container: without } = renderBin({ canDelete: false });
    const headerWithout = without.firstElementChild!.firstElementChild!;

    granted = { "download:asset": true };
    const { container: withIcons } = renderBin({ canDelete: true });
    const headerWith = withIcons.firstElementChild!.firstElementChild!;

    // Sanity: we grabbed the header rows
    expect(headerWithout.textContent).toContain("common.clear");
    expect(headerWith.textContent).toContain("common.clear");

    // Both headers carry the same, non-empty minHeight rule
    const minHeightWithout = getComputedStyle(headerWithout).minHeight;
    const minHeightWith = getComputedStyle(headerWith).minHeight;
    expect(minHeightWithout).toBe(minHeightWith);
    expect(minHeightWithout).not.toBe("");
  });
});
