import React, { useCallback } from "react";
import { useGetFavorites, useAddFavorite, useRemoveFavorite } from "../api/hooks/useFavorites";

export interface CollectionFavoriteMetadata {
  name?: string;
  isPublic?: boolean;
  itemCount?: number;
  childCollectionCount?: number;
  collectionTypeId?: string;
  thumbnailType?: string;
  thumbnailValue?: string;
  thumbnailUrl?: string;
}

const ITEM_TYPE = "COLLECTION" as const;

export function useCollectionFavorites() {
  const { data: favorites } = useGetFavorites(ITEM_TYPE);
  const { mutate: addFavorite } = useAddFavorite();
  const { mutate: removeFavorite } = useRemoveFavorite();

  const isCollectionFavorited = useCallback(
    (collectionId: string) => !!favorites?.some((favorite) => favorite.itemId === collectionId),
    [favorites]
  );

  const handleFavoriteToggle = useCallback(
    (
      collection: { id: string; name?: string } & CollectionFavoriteMetadata,
      event: React.MouseEvent<HTMLElement>
    ) => {
      event.stopPropagation();
      if (isCollectionFavorited(collection.id)) {
        removeFavorite({ itemType: ITEM_TYPE, itemId: collection.id });
      } else {
        addFavorite({
          itemId: collection.id,
          itemType: ITEM_TYPE,
          metadata: {
            name: collection.name ?? "",
            isPublic: collection.isPublic ?? false,
            itemCount: collection.itemCount ?? 0,
            childCollectionCount: collection.childCollectionCount ?? 0,
            collectionTypeId: collection.collectionTypeId,
            thumbnailType: collection.thumbnailType,
            thumbnailValue: collection.thumbnailValue,
            thumbnailUrl: collection.thumbnailUrl,
          },
        });
      }
    },
    [isCollectionFavorited, addFavorite, removeFavorite]
  );

  return { favorites, isCollectionFavorited, handleFavoriteToggle };
}
