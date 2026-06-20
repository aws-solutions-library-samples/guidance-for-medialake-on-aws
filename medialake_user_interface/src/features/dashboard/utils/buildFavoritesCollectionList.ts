import type { Collection } from "@/api/hooks/useCollections";
import type { Favorite } from "@/api/hooks/useFavorites";
import type { SortConfig } from "../types";
import { filterCollections, sortCollections } from "./collectionFilters";
import { favoriteToCollectionCardData } from "./favoriteToCollectionCardData";

/**
 * Builds the favorites-view collection list using the "join + metadata fallback"
 * strategy described in the design.
 *
 * 1. Union every loaded dataset (standard, shared-with-me, shared-by-me) into a
 *    de-duplicated candidate pool (first occurrence wins).
 * 2. Join: keep the favorited collections present in the pool as full objects,
 *    sorted via `sortCollections`.
 * 3. Fallback append: for any favorited id not present in the pool (e.g. a
 *    favorited shared collection not in the current page), append a card built
 *    from the `Favorite.metadata` captured when it was favorited.
 *
 * The live pool object always wins over the captured metadata for ids present in
 * both, so favorites never render with stale data when the real object is loaded.
 *
 * @param datasets - The loaded collection datasets to union into the pool.
 * @param favorites - The current user's COLLECTION favorites.
 * @param currentUserId - The current user id (passed through to filterCollections).
 * @param sorting - Sort configuration applied to the joined collections.
 * @returns Favorited collections: joined (sorted) first, then fallback cards.
 */
export function buildFavoritesCollectionList(
  datasets: Collection[][],
  favorites: Favorite[],
  currentUserId: string,
  sorting: SortConfig
): Collection[] {
  const favoritedIds = new Set(favorites.map((fav) => fav.itemId));

  // Union datasets into a de-duplicated pool (first occurrence wins).
  const seen = new Set<string>();
  const pool: Collection[] = [];
  for (const dataset of datasets) {
    for (const collection of dataset) {
      if (!seen.has(collection.id)) {
        seen.add(collection.id);
        pool.push(collection);
      }
    }
  }

  // Join: favorited collections present in the pool, as full objects, sorted.
  const joined = sortCollections(
    filterCollections(pool, "favorites", currentUserId, favoritedIds),
    sorting
  );
  const joinedIds = new Set(joined.map((collection) => collection.id));

  // Fallback append: favorited ids not present in the pool, from captured metadata.
  const fallback = favorites
    .filter((fav) => !joinedIds.has(fav.itemId))
    .map((fav) => favoriteToCollectionCardData(fav));

  return [...joined, ...fallback];
}
