import type { Favorite } from "@/api/hooks/useFavorites";
import type { Collection } from "@/api/hooks/useCollections";

/**
 * Maps a COLLECTION favorite into a complete Collection object using captured
 * metadata, with safe defaults for the required fields not present in
 * Favorite.metadata.
 *
 * This allows favorited collections that are absent from the currently loaded
 * dataset (e.g. favorited shared collections) to render in CollectionCard or
 * CollectionCardSimple without type errors.
 *
 * Safe default rationale:
 * - createdAt/updatedAt as "" — CollectionCard guards date rendering with a
 *   truthy check, so empty strings are simply skipped.
 * - type derived from isPublic — the card reads visibility from isPublic, so
 *   the derived type stays consistent.
 * - ownerId: "" — fallback cards are rendered without mutation handlers, so no
 *   owner-only action menu appears regardless of inferred ownership.
 * - status: "active" — safe neutral value; inactive collections are not
 *   favorited in practice.
 */
export function favoriteToCollectionCardData(fav: Favorite): Collection {
  const m = (fav.metadata ?? {}) as Record<string, unknown>;
  const isPublic = (m.isPublic as boolean | undefined) ?? false;

  return {
    id: fav.itemId,
    name: (m.name as string | undefined) ?? fav.itemId,
    // Required fields with safe defaults (not carried in favorite metadata):
    type: isPublic ? "public" : "private",
    ownerId: "",
    status: "active",
    childCount: (m.childCount as number | undefined) ?? 0,
    createdAt: "",
    updatedAt: "",
    // Fields carried in metadata:
    isPublic,
    itemCount: (m.itemCount as number | undefined) ?? 0,
    childCollectionCount: (m.childCollectionCount as number | undefined) ?? 0,
    collectionTypeId: m.collectionTypeId as string | undefined,
    thumbnailType: m.thumbnailType as Collection["thumbnailType"],
    thumbnailValue: m.thumbnailValue as string | undefined,
    thumbnailUrl: m.thumbnailUrl as string | undefined,
  };
}
