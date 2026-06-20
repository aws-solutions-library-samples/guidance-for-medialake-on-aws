import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import type { Collection } from "../../api/hooks/useCollections";
import {
  DEFAULT_PREFS,
  type CollectionCardDisplayPrefs,
  type CollectionCardPreset,
  type CollectionCardSize,
} from "../../hooks/useCollectionViewPreferences";

// i18n: pass through fallback strings so assertions don't rely on a real bundle.
// Return the inline fallback when provided, otherwise the key itself — so labels
// sourced from i18n keys without an inline default (e.g. the favorite toggle's
// `favorites.*` aria-labels) are still assertable.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

vi.mock("./ThumbnailSelector", () => ({
  ALL_ICONS: {},
}));

import { CollectionCard } from "./CollectionCard";

const makeCollection = (overrides: Partial<Collection> = {}): Collection => ({
  id: "col-1",
  name: "Test Collection",
  description: "A collection that holds test assets.",
  type: "private",
  ownerId: "user-1",
  itemCount: 3,
  childCount: 0,
  childCollectionCount: 0,
  isPublic: false,
  status: "active",
  userRole: "owner",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-06-15T00:00:00Z",
  tags: ["featured", "q3", "editorial"],
  customMetadata: {
    priority: "high",
    client: "Acme Corp",
    episode: "101",
  },
  ...overrides,
});

const makePrefs = (
  overrides: Partial<CollectionCardDisplayPrefs> = {}
): CollectionCardDisplayPrefs => ({
  ...DEFAULT_PREFS,
  visibleMetadataKeys: ["priority", "client", "episode"],
  ...overrides,
});

describe("CollectionCard — metadata strip", () => {
  it("renders selected customMetadata keys as key:value chips", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        display={makePrefs({ preset: "rich", maxMetadataKeys: 3 })}
      />
    );

    expect(screen.getByLabelText("priority: high")).toBeInTheDocument();
    expect(screen.getByLabelText("client: Acme Corp")).toBeInTheDocument();
    expect(screen.getByLabelText("episode: 101")).toBeInTheDocument();
  });

  it("caps metadata by maxMetadataKeys and shows a +N overflow chip", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        display={makePrefs({ preset: "rich", maxMetadataKeys: 2 })}
      />
    );

    expect(screen.getByLabelText("priority: high")).toBeInTheDocument();
    expect(screen.getByLabelText("client: Acme Corp")).toBeInTheDocument();
    expect(screen.queryByLabelText("episode: 101")).not.toBeInTheDocument();
    // Overflow chip for the one key we dropped
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("skips keys that have no value on this collection", () => {
    render(
      <CollectionCard
        collection={makeCollection({
          customMetadata: { priority: "high" }, // client/episode absent
        })}
        onClick={vi.fn()}
        display={makePrefs({ preset: "rich", maxMetadataKeys: 3 })}
      />
    );

    expect(screen.getByLabelText("priority: high")).toBeInTheDocument();
    expect(screen.queryByLabelText(/client:/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/episode:/)).not.toBeInTheDocument();
  });

  it("does not render any metadata when maxMetadataKeys=0", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        display={makePrefs({ preset: "compact", maxMetadataKeys: 0 })}
      />
    );

    expect(screen.queryByLabelText(/priority:/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/client:/)).not.toBeInTheDocument();
  });

  it("falls back to the collection's own keys when visibleMetadataKeys is empty", () => {
    // User hasn't curated any keys yet (e.g. fresh install, metadata-keys
    // endpoint hasn't seeded the list). Rich preset should still surface
    // metadata from the collection itself so the feature is self-explaining.
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        display={makePrefs({
          preset: "rich",
          maxMetadataKeys: 3,
          visibleMetadataKeys: [],
        })}
      />
    );

    // Alphabetical order: client, episode, priority
    expect(screen.getByLabelText("client: Acme Corp")).toBeInTheDocument();
    expect(screen.getByLabelText("episode: 101")).toBeInTheDocument();
    expect(screen.getByLabelText("priority: high")).toBeInTheDocument();
  });

  it("fallback respects maxMetadataKeys=0 (minimal/compact presets)", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        display={makePrefs({
          preset: "compact",
          maxMetadataKeys: 0,
          visibleMetadataKeys: [],
        })}
      />
    );

    expect(screen.queryByLabelText(/priority:/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/client:/)).not.toBeInTheDocument();
  });
});

describe("CollectionCard — presets", () => {
  const collection = makeCollection();

  it("full preset shows description, tags, metadata, visibility chip, and meta row", () => {
    render(
      <CollectionCard
        collection={collection}
        onClick={vi.fn()}
        display={makePrefs({
          preset: "full",
          showDescription: true,
          showTags: true,
          showMeta: true,
          showVisibility: true,
          maxMetadataKeys: 20,
        })}
      />
    );

    expect(screen.getByText(/holds test assets/i)).toBeInTheDocument();
    expect(screen.getByText("featured")).toBeInTheDocument();
    expect(screen.getByLabelText("priority: high")).toBeInTheDocument();
    // Visibility chip (Private)
    expect(screen.getByText("Private")).toBeInTheDocument();
    // Meta row has asset count
    expect(screen.getByText(/3 assets/)).toBeInTheDocument();
  });

  it("compact preset hides description and metadata but keeps tags, meta, visibility", () => {
    render(
      <CollectionCard
        collection={collection}
        onClick={vi.fn()}
        display={makePrefs({
          preset: "compact",
          showDescription: false,
          showTags: true,
          showMeta: true,
          showVisibility: true,
          maxMetadataKeys: 0,
        })}
      />
    );

    expect(screen.queryByText(/holds test assets/i)).not.toBeInTheDocument();
    expect(screen.getByText("featured")).toBeInTheDocument();
    expect(screen.queryByLabelText("priority: high")).not.toBeInTheDocument();
    expect(screen.getByText("Private")).toBeInTheDocument();
    expect(screen.getByText(/3 assets/)).toBeInTheDocument();
  });

  it("minimal preset shows only name, hides tags/description/meta", () => {
    render(
      <CollectionCard
        collection={collection}
        onClick={vi.fn()}
        display={makePrefs({
          preset: "minimal",
          showDescription: false,
          showTags: false,
          showMeta: false,
          showVisibility: true,
          showParentBreadcrumb: false,
          maxMetadataKeys: 0,
        })}
      />
    );

    expect(screen.getByText("Test Collection")).toBeInTheDocument();
    expect(screen.queryByText(/holds test assets/i)).not.toBeInTheDocument();
    expect(screen.queryByText("featured")).not.toBeInTheDocument();
    expect(screen.queryByText(/3 assets/)).not.toBeInTheDocument();
    // In minimal, visibility is a corner dot — the visibility chip is not rendered.
    expect(screen.queryByText("Private")).not.toBeInTheDocument();
    // But the corner dot is, with an aria-label reflecting the visibility.
    expect(screen.getByLabelText("Private")).toBeInTheDocument();
  });
});

describe("CollectionCard — card size", () => {
  const sizes: CollectionCardSize[] = ["small", "medium", "large"];

  it.each(sizes)("renders successfully at size=%s", (size) => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        display={makePrefs({ cardSize: size })}
      />
    );

    expect(screen.getByText("Test Collection")).toBeInTheDocument();
  });
});

describe("CollectionCard — sortedMetadataKey explainer", () => {
  it("does not double-render a value already shown in the metadata strip", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        sortedMetadataKey="priority"
        display={makePrefs({ preset: "rich", maxMetadataKeys: 3 })}
      />
    );

    // Strip renders the raw key:value pair.
    expect(screen.getByLabelText("priority: high")).toBeInTheDocument();
    // The "priority · high" explainer chip should NOT also render.
    expect(screen.queryByText("priority · high")).not.toBeInTheDocument();
  });

  it("shows the explainer chip in minimal preset when a metadata sort is active", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        sortedMetadataKey="priority"
        display={makePrefs({
          preset: "minimal",
          showDescription: false,
          showTags: false,
          showMeta: false,
          showParentBreadcrumb: false,
          maxMetadataKeys: 0,
        })}
      />
    );

    expect(screen.getByText("priority · high")).toBeInTheDocument();
  });
});

describe("CollectionCard — defaults", () => {
  it("renders safely without a display prop (default rich profile)", () => {
    render(<CollectionCard collection={makeCollection()} onClick={vi.fn()} />);
    expect(screen.getByText("Test Collection")).toBeInTheDocument();
  });
});

// Sanity check that every non-custom preset is covered by the rendering tests.
// Catches the case where someone adds a new preset but forgets the assertions.
describe("CollectionCard — preset coverage", () => {
  const knownPresets: CollectionCardPreset[] = ["full", "rich", "compact", "minimal", "custom"];

  it("accepts every preset enum value without throwing", () => {
    for (const preset of knownPresets) {
      const { unmount } = render(
        <CollectionCard
          collection={makeCollection()}
          onClick={vi.fn()}
          display={makePrefs({ preset })}
        />
      );
      expect(screen.getAllByText("Test Collection").length).toBeGreaterThan(0);
      unmount();
    }
  });
});

describe("CollectionCard — favorite toggle", () => {
  it("does not render the toggle when onFavoriteToggle is not provided", () => {
    render(<CollectionCard collection={makeCollection()} onClick={vi.fn()} />);
    expect(screen.queryByTestId("collection-favorite-button")).not.toBeInTheDocument();
  });

  it("renders the toggle when onFavoriteToggle is provided", () => {
    render(
      <CollectionCard collection={makeCollection()} onClick={vi.fn()} onFavoriteToggle={vi.fn()} />
    );
    expect(screen.getByTestId("collection-favorite-button")).toBeInTheDocument();
  });

  it("shows the filled icon and remove-from-favorites label when favorited", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        isFavorite
        onFavoriteToggle={vi.fn()}
      />
    );
    const button = screen.getByTestId("collection-favorite-button");
    expect(button).toHaveAttribute("aria-label", "favorites.removeFavorite");
    expect(screen.getByTestId("FavoriteIcon")).toBeInTheDocument();
    expect(screen.queryByTestId("FavoriteBorderIcon")).not.toBeInTheDocument();
  });

  it("shows the outline icon and add-to-favorites label when not favorited", () => {
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={vi.fn()}
        isFavorite={false}
        onFavoriteToggle={vi.fn()}
      />
    );
    const button = screen.getByTestId("collection-favorite-button");
    expect(button).toHaveAttribute("aria-label", "favorites.addFavorite");
    expect(screen.getByTestId("FavoriteBorderIcon")).toBeInTheDocument();
    expect(screen.queryByTestId("FavoriteIcon")).not.toBeInTheDocument();
  });

  it("invokes onFavoriteToggle and does NOT trigger card navigation (click isolation)", () => {
    const onClick = vi.fn();
    const onFavoriteToggle = vi.fn();
    render(
      <CollectionCard
        collection={makeCollection()}
        onClick={onClick}
        onFavoriteToggle={onFavoriteToggle}
      />
    );
    fireEvent.click(screen.getByTestId("collection-favorite-button"));
    expect(onFavoriteToggle).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });
});
