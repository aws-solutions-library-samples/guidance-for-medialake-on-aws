import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

import { CollectionFavoriteButton } from "./CollectionFavoriteButton";

describe("CollectionFavoriteButton", () => {
  it("renders a button", () => {
    render(<CollectionFavoriteButton isFavorite={false} onToggle={vi.fn()} />);
    expect(screen.getByTestId("collection-favorite-button")).toBeInTheDocument();
  });

  it("shows the filled icon and remove-from-favorites label when favorited", () => {
    render(<CollectionFavoriteButton isFavorite onToggle={vi.fn()} />);
    const button = screen.getByTestId("collection-favorite-button");
    expect(button).toHaveAttribute("aria-label", "favorites.removeFavorite");
    expect(screen.getByTestId("FavoriteIcon")).toBeInTheDocument();
    expect(screen.queryByTestId("FavoriteBorderIcon")).not.toBeInTheDocument();
  });

  it("shows the outline icon and add-to-favorites label when not favorited", () => {
    render(<CollectionFavoriteButton isFavorite={false} onToggle={vi.fn()} />);
    const button = screen.getByTestId("collection-favorite-button");
    expect(button).toHaveAttribute("aria-label", "favorites.addFavorite");
    expect(screen.getByTestId("FavoriteBorderIcon")).toBeInTheDocument();
    expect(screen.queryByTestId("FavoriteIcon")).not.toBeInTheDocument();
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(<CollectionFavoriteButton isFavorite={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByTestId("collection-favorite-button"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});
