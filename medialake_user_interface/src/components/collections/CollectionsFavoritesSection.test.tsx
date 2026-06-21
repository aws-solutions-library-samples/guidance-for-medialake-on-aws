import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import React from "react";
import type { Collection } from "../../api/hooks/useCollections";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

import { CollectionsFavoritesSection } from "./CollectionsFavoritesSection";

const makeCollection = (overrides: Partial<Collection> = {}): Collection => ({
  id: "c1",
  name: "Test Collection",
  type: "private",
  ownerId: "user-1",
  itemCount: 0,
  childCount: 0,
  childCollectionCount: 0,
  isPublic: false,
  status: "active",
  createdAt: "",
  updatedAt: "",
  ...overrides,
});

describe("CollectionsFavoritesSection", () => {
  it("renders the 'Favorites' section heading", () => {
    render(
      <CollectionsFavoritesSection favorites={[]} isLive={() => true} renderCard={() => null} />
    );
    expect(screen.getByRole("heading", { name: "Favorites" })).toBeInTheDocument();
  });

  it("shows the empty state when there are no favorites", () => {
    render(
      <CollectionsFavoritesSection favorites={[]} isLive={() => true} renderCard={() => null} />
    );
    expect(screen.getByText("No Favorite Collections")).toBeInTheDocument();
    expect(screen.getByText("Collections you favorite will appear here")).toBeInTheDocument();
    expect(screen.queryByTestId("favorites-grid")).not.toBeInTheDocument();
  });

  it("renders one card per favorite inside the grid", () => {
    const favorites = [
      makeCollection({ id: "a", name: "Apple" }),
      makeCollection({ id: "b", name: "Banana" }),
    ];
    render(
      <CollectionsFavoritesSection
        favorites={favorites}
        isLive={() => true}
        renderCard={(c) => <div key={c.id}>{c.name}</div>}
      />
    );
    const grid = screen.getByTestId("favorites-grid");
    expect(within(grid).getByText("Apple")).toBeInTheDocument();
    expect(within(grid).getByText("Banana")).toBeInTheDocument();
    expect(screen.queryByText("No Favorite Collections")).not.toBeInTheDocument();
  });

  it("passes the isLive result as withActions to renderCard per favorite", () => {
    const renderCard = vi.fn((c: Collection) => <div key={c.id}>{c.name}</div>);
    const favorites = [
      makeCollection({ id: "live", name: "Live" }),
      makeCollection({ id: "fallback", name: "Fallback" }),
    ];
    render(
      <CollectionsFavoritesSection
        favorites={favorites}
        isLive={(id) => id === "live"}
        renderCard={renderCard}
      />
    );
    expect(renderCard).toHaveBeenCalledWith(favorites[0], true);
    expect(renderCard).toHaveBeenCalledWith(favorites[1], false);
  });
});
