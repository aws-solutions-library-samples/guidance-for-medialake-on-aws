import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// i18n: return the inline fallback when provided, otherwise the key itself — so
// labels sourced from i18n keys without an inline default (the favorite toggle's
// `favorites.*` aria-labels) are still assertable.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

vi.mock("@/components/collections/ThumbnailSelector", () => ({
  ALL_ICONS: {},
}));

import { CollectionCardSimple } from "./CollectionCardSimple";

const baseProps = {
  name: "Test Collection",
  itemCount: 3,
  isPublic: false,
  onClick: vi.fn(),
};

describe("CollectionCardSimple — favorite toggle", () => {
  it("does not render the toggle when onFavoriteToggle is not provided", () => {
    render(<CollectionCardSimple {...baseProps} />);
    expect(screen.queryByTestId("collection-favorite-button")).not.toBeInTheDocument();
  });

  it("renders the toggle when onFavoriteToggle is provided", () => {
    render(<CollectionCardSimple {...baseProps} onFavoriteToggle={vi.fn()} />);
    expect(screen.getByTestId("collection-favorite-button")).toBeInTheDocument();
  });

  it("shows the filled icon and remove-from-favorites label when favorited", () => {
    render(<CollectionCardSimple {...baseProps} isFavorite onFavoriteToggle={vi.fn()} />);
    const button = screen.getByTestId("collection-favorite-button");
    expect(button).toHaveAttribute("aria-label", "favorites.removeFavorite");
    expect(screen.getByTestId("FavoriteIcon")).toBeInTheDocument();
    expect(screen.queryByTestId("FavoriteBorderIcon")).not.toBeInTheDocument();
  });

  it("shows the outline icon and add-to-favorites label when not favorited", () => {
    render(<CollectionCardSimple {...baseProps} isFavorite={false} onFavoriteToggle={vi.fn()} />);
    const button = screen.getByTestId("collection-favorite-button");
    expect(button).toHaveAttribute("aria-label", "favorites.addFavorite");
    expect(screen.getByTestId("FavoriteBorderIcon")).toBeInTheDocument();
    expect(screen.queryByTestId("FavoriteIcon")).not.toBeInTheDocument();
  });

  it("invokes onFavoriteToggle and does NOT trigger card navigation (click isolation)", () => {
    const onClick = vi.fn();
    const onFavoriteToggle = vi.fn();
    render(
      <CollectionCardSimple {...baseProps} onClick={onClick} onFavoriteToggle={onFavoriteToggle} />
    );
    fireEvent.click(screen.getByTestId("collection-favorite-button"));
    expect(onFavoriteToggle).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });
});
