import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// ---- i18n: fallback ?? key so favorite aria-labels are assertable ----
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string, fallback?: string) => fallback ?? key }),
}));

// ---- routing ----
vi.mock("react-router", () => ({ useNavigate: () => vi.fn() }));

// ---- auth / jwt: resolve a stable current user id ----
vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: () => Promise.resolve({ tokens: { idToken: { toString: () => "token" } } }),
}));
vi.mock("jwt-decode", () => ({ jwtDecode: () => ({ sub: "user-1" }) }));

// ---- dashboard store ----
vi.mock("../../store/dashboardStore", () => ({
  useDashboardStore: (_selector: unknown) => undefined,
  useDashboardActions: () => ({
    removeWidget: vi.fn(),
    setExpandedWidget: vi.fn(),
    updateWidgetConfig: vi.fn(),
    updateWidgetCustomName: vi.fn(),
  }),
}));

// ---- thumbnail catalog used by CollectionCardSimple ----
vi.mock("@/components/collections/ThumbnailSelector", () => ({ ALL_ICONS: {} }));

// ---- heavy wrappers: passthroughs so we can assert title + cards ----
vi.mock("../WidgetContainer", () => ({
  WidgetContainer: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}));
vi.mock("../CollectionCarousel", () => ({
  CollectionCarousel: ({
    items,
    renderCard,
    getItemKey,
    emptyState,
  }: {
    items: any[];
    renderCard: (item: any) => React.ReactNode;
    getItemKey: (item: any) => string;
    emptyState: React.ReactNode;
  }) =>
    items.length === 0 ? (
      <>{emptyState}</>
    ) : (
      <div>
        {items.map((item) => (
          <div key={getItemKey(item)}>{renderCard(item)}</div>
        ))}
      </div>
    ),
}));
vi.mock("./WidgetConfigPanel", () => ({ WidgetConfigPanel: () => null }));

// ---- data hooks ----
const useGetCollections = vi.fn();
const useGetCollectionTypes = vi.fn();
const useGetCollectionsSharedWithMe = vi.fn();
const useGetCollectionsSharedByMe = vi.fn();
vi.mock("@/api/hooks/useCollections", () => ({
  useGetCollections: (...a: unknown[]) => useGetCollections(...a),
  useGetCollectionTypes: (...a: unknown[]) => useGetCollectionTypes(...a),
  useGetCollectionsSharedWithMe: (...a: unknown[]) => useGetCollectionsSharedWithMe(...a),
  useGetCollectionsSharedByMe: (...a: unknown[]) => useGetCollectionsSharedByMe(...a),
}));

// ---- favorites hooks (the real useCollectionFavorites runs on top of these) ----
const useGetFavorites = vi.fn();
const addMutate = vi.fn();
const removeMutate = vi.fn();
vi.mock("@/api/hooks/useFavorites", () => ({
  useGetFavorites: (...a: unknown[]) => useGetFavorites(...a),
  useAddFavorite: () => ({ mutate: addMutate }),
  useRemoveFavorite: () => ({ mutate: removeMutate }),
}));

import { CollectionsWidget } from "./CollectionsWidget";
import type { CollectionsWidgetConfig } from "../../types";

const favoritesConfig: CollectionsWidgetConfig = {
  viewType: "favorites",
  sorting: { sortBy: "name", sortOrder: "asc" },
};

const okList = (data: unknown[]) => ({
  data: { data },
  isLoading: false,
  error: null,
  refetch: vi.fn(),
});

beforeEach(() => {
  vi.clearAllMocks();
  // Standard dataset contains one collection; the shared datasets are empty.
  useGetCollections.mockReturnValue(
    okList([
      {
        id: "a",
        name: "Apple",
        type: "private",
        ownerId: "user-1",
        itemCount: 1,
        childCount: 0,
        childCollectionCount: 0,
        isPublic: false,
        status: "active",
        createdAt: "",
        updatedAt: "",
      },
    ])
  );
  useGetCollectionsSharedWithMe.mockReturnValue(okList([]));
  useGetCollectionsSharedByMe.mockReturnValue(okList([]));
  useGetCollectionTypes.mockReturnValue({ data: { data: [] }, isLoading: false });
});

describe("CollectionsWidget — favorites view", () => {
  it("shows the 'Favorite Collections' title", async () => {
    useGetFavorites.mockReturnValue({ data: [] });
    render(<CollectionsWidget widgetId="w1" config={favoritesConfig} />);
    expect(
      await screen.findByRole("heading", { name: "Favorite Collections" })
    ).toBeInTheDocument();
  });

  it("renders favorited collections and excludes non-favorited ones", async () => {
    useGetFavorites.mockReturnValue({
      data: [{ itemId: "a", itemType: "COLLECTION", metadata: { name: "Apple" } }],
    });
    render(<CollectionsWidget widgetId="w1" config={favoritesConfig} />);
    expect(await screen.findByText("Apple")).toBeInTheDocument();
  });

  it("renders a favorited collection absent from every dataset via the metadata fallback", async () => {
    useGetFavorites.mockReturnValue({
      data: [
        { itemId: "a", itemType: "COLLECTION", metadata: { name: "Apple" } },
        // 'z' is favorited but in no loaded dataset (e.g. a favorited shared collection).
        { itemId: "z", itemType: "COLLECTION", metadata: { name: "Zebra", itemCount: 4 } },
      ],
    });
    render(<CollectionsWidget widgetId="w1" config={favoritesConfig} />);
    expect(await screen.findByText("Apple")).toBeInTheDocument();
    expect(screen.getByText("Zebra")).toBeInTheDocument();
  });

  it("shows the favorites empty-state when the user has no favorited collections", async () => {
    useGetFavorites.mockReturnValue({ data: [] });
    render(<CollectionsWidget widgetId="w1" config={favoritesConfig} />);
    expect(await screen.findByText("No Favorite Collections")).toBeInTheDocument();
  });

  it("requests favorites filtered by itemType=COLLECTION", async () => {
    useGetFavorites.mockReturnValue({ data: [] });
    render(<CollectionsWidget widgetId="w1" config={favoritesConfig} />);
    await screen.findByRole("heading", { name: "Favorite Collections" });
    expect(useGetFavorites).toHaveBeenCalledWith("COLLECTION");
  });
});
