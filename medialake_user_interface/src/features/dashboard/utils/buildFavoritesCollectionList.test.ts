import { describe, it, expect } from "vitest";
import { buildFavoritesCollectionList } from "./buildFavoritesCollectionList";
import type { Collection } from "@/api/hooks/useCollections";
import type { Favorite } from "@/api/hooks/useFavorites";
import type { SortConfig } from "../types";

const sorting: SortConfig = { sortBy: "name", sortOrder: "asc" };

const makeCollection = (overrides: Partial<Collection> = {}): Collection => ({
  id: "c1",
  name: "Collection 1",
  type: "private",
  ownerId: "user-1",
  itemCount: 0,
  childCount: 0,
  childCollectionCount: 0,
  isPublic: false,
  status: "active",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  ...overrides,
});

const makeFavorite = (itemId: string, metadata: Record<string, unknown> = {}): Favorite => ({
  itemId,
  itemType: "COLLECTION",
  metadata: { name: `Fav ${itemId}`, ...metadata },
  addedAt: "2024-01-01T00:00:00Z",
});

describe("buildFavoritesCollectionList", () => {
  it("returns only favorited collections present in the pool (join)", () => {
    const standard = [
      makeCollection({ id: "a", name: "Apple" }),
      makeCollection({ id: "b", name: "Banana" }),
      makeCollection({ id: "c", name: "Cherry" }),
    ];
    const favorites = [makeFavorite("a"), makeFavorite("c")];

    const result = buildFavoritesCollectionList([standard], favorites, "user-1", sorting);

    expect(result.map((c) => c.id)).toEqual(["a", "c"]);
  });

  it("excludes collections that are not favorited", () => {
    const standard = [makeCollection({ id: "a" }), makeCollection({ id: "b" })];
    const favorites = [makeFavorite("a")];

    const result = buildFavoritesCollectionList([standard], favorites, "user-1", sorting);

    expect(result.map((c) => c.id)).toEqual(["a"]);
  });

  it("dedupes a collection that appears in more than one dataset", () => {
    const shared = makeCollection({ id: "x", name: "Shared" });
    // Same id present in both the standard and shared-with-me datasets.
    const result = buildFavoritesCollectionList(
      [[shared], [shared]],
      [makeFavorite("x")],
      "user-1",
      sorting
    );

    expect(result.filter((c) => c.id === "x")).toHaveLength(1);
  });

  it("appends a metadata fallback card for a favorited id absent from every dataset", () => {
    const standard = [makeCollection({ id: "a", name: "Apple" })];
    // 'z' is favorited but not in any loaded dataset (e.g. a favorited shared collection).
    const favorites = [
      makeFavorite("a"),
      makeFavorite("z", { name: "Zebra", itemCount: 7, isPublic: true }),
    ];

    const result = buildFavoritesCollectionList([standard], favorites, "user-1", sorting);

    const ids = result.map((c) => c.id);
    expect(ids).toContain("z");
    const fallback = result.find((c) => c.id === "z")!;
    expect(fallback.name).toBe("Zebra");
    expect(fallback.itemCount).toBe(7);
    expect(fallback.isPublic).toBe(true);
  });

  it("does not duplicate a favorited id that exists in the pool with a fallback card", () => {
    const standard = [makeCollection({ id: "a", name: "Apple" })];
    const favorites = [makeFavorite("a", { name: "Stale Name" })];

    const result = buildFavoritesCollectionList([standard], favorites, "user-1", sorting);

    expect(result.filter((c) => c.id === "a")).toHaveLength(1);
    // The live (pool) object wins over the captured metadata.
    expect(result.find((c) => c.id === "a")!.name).toBe("Apple");
  });

  it("orders joined (sorted) collections first, then appended fallback cards", () => {
    const standard = [
      makeCollection({ id: "b", name: "Banana" }),
      makeCollection({ id: "a", name: "Apple" }),
    ];
    const favorites = [makeFavorite("b"), makeFavorite("a"), makeFavorite("z", { name: "Zebra" })];

    const result = buildFavoritesCollectionList([standard], favorites, "user-1", sorting);

    // Apple, Banana (sorted joined) then Zebra (fallback).
    expect(result.map((c) => c.id)).toEqual(["a", "b", "z"]);
  });

  it("returns an empty list when there are no favorites", () => {
    const standard = [makeCollection({ id: "a" })];
    const result = buildFavoritesCollectionList([standard], [], "user-1", sorting);
    expect(result).toEqual([]);
  });
});
