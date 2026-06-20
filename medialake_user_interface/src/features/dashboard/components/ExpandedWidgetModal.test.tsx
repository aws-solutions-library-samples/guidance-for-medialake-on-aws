import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDashboardStore } from "../store/dashboardStore";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback || _key }),
}));

// Stub widget components to avoid pulling in their full dependency trees
vi.mock("./widgets/FavoritesWidget", () => ({ FavoritesWidget: () => <div>FavoritesStub</div> }));
vi.mock("./widgets/CollectionsWidget", () => ({
  CollectionsWidget: () => <div>CollectionsStub</div>,
}));
vi.mock("./widgets/RecentAssetsWidget", () => ({
  RecentAssetsWidget: () => <div>RecentAssetsStub</div>,
}));
vi.mock("./widgets/CollectionGroupWidget", () => ({
  CollectionGroupWidget: () => <div>CollectionGroupStub</div>,
}));
vi.mock("./widgets/MyAssetsWidget", () => ({ MyAssetsWidget: () => <div>MyAssetsStub</div> }));

import { ExpandedWidgetModal } from "./ExpandedWidgetModal";

describe("ExpandedWidgetModal with my-assets", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    localStorage.clear();
    useDashboardStore.getState().resetToDefault();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  });

  function renderModal() {
    return render(
      <QueryClientProvider client={queryClient}>
        <ExpandedWidgetModal />
      </QueryClientProvider>
    );
  }

  it("renders modal header with My Assets title when my-assets widget is expanded", () => {
    const store = useDashboardStore.getState();
    store.addWidget("my-assets");
    const widget = useDashboardStore.getState().layout.widgets.find((w) => w.type === "my-assets")!;
    store.setExpandedWidget(widget.id);

    renderModal();

    expect(screen.getByText("My Assets")).toBeInTheDocument();
  });

  it("invalidates search query key when refresh is clicked for my-assets", async () => {
    const store = useDashboardStore.getState();
    store.addWidget("my-assets");
    const widget = useDashboardStore.getState().layout.widgets.find((w) => w.type === "my-assets")!;
    store.setExpandedWidget(widget.id);

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    renderModal();

    await userEvent.click(screen.getByLabelText("dashboard.actions.refresh"));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["search"] });
  });
});
