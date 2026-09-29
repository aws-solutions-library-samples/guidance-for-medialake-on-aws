import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithUser } from "@/test/render";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string, opts?: Record<string, unknown>) =>
      (fallback ?? key).replace(/\{\{(\w+)\}\}/g, (_m, k) => String(opts?.[k] ?? "")),
  }),
}));
vi.mock("../../store/dashboardStore", () => ({
  useDashboardStore: () => undefined,
  useDashboardActions: () => ({ removeWidget: vi.fn(), setExpandedWidget: vi.fn() }),
}));
vi.mock("../WidgetContainer", () => ({
  WidgetContainer: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}));

const useSavedSearches = vi.fn();
vi.mock("@/features/search-history/api", () => ({
  useSavedSearches: (...a: unknown[]) => useSavedSearches(...a),
}));
const runSearch = vi.fn();
vi.mock("@/features/search-history/hooks", () => ({ useRunSearch: () => runSearch }));

import { SavedSearchesWidget } from "./SavedSearchesWidget";

const item = {
  id: "s1",
  name: "Sunset videos",
  definition: { v: 1, q: "sunset", semantic: false, filters: { type: "Video" } },
  fingerprint: "f",
  createdAt: "2026-09-01T00:00:00Z",
  updatedAt: "2026-09-01T00:00:00Z",
};

describe("SavedSearchesWidget", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists saved searches and runs one when clicked", async () => {
    useSavedSearches.mockReturnValue({
      data: [item],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    const { user } = renderWithUser(<SavedSearchesWidget widgetId="w1" />);
    expect(await screen.findByRole("heading", { name: "Saved Searches" })).toBeInTheDocument();
    expect(screen.getByText("sunset · Video")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Sunset videos/ }));
    expect(runSearch).toHaveBeenCalledWith(item.definition);
  });

  it("explains how to save a search when there are none", () => {
    useSavedSearches.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithUser(<SavedSearchesWidget widgetId="w1" />);
    expect(screen.getByText("No saved searches")).toBeInTheDocument();
  });
});
