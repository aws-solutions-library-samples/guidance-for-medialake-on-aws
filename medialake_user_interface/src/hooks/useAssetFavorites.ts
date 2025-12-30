import React, { useCallback } from "react";
import { useGetFavorites, useAddFavorite, useRemoveFavorite } from "../api/hooks/useFavorites";

export function useAssetFavorites<T>({
  getAssetId,
  getAssetName,
  getAssetType,
  getAssetThumbnail,
}: {
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
}) {
  const { data: favorites } = useGetFavorites("ASSET");
  const { mutate: addFavorite } = useAddFavorite();
  const { mutate: removeFavorite } = useRemoveFavorite();

  const isAssetFavorited = useCallback(
    (assetId: string) => {
      if (!favorites) return false;
      return favorites.some((favorite) => favorite.itemId === assetId);
    },
    [favorites]
  );

  const handleFavoriteToggle = useCallback(
    (asset: T, event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();

      const assetId = getAssetId(asset);

      if (isAssetFavorited(assetId)) {
        removeFavorite({ itemType: "ASSET", itemId: assetId });
      } else {
        addFavorite({
          itemId: assetId,
          itemType: "ASSET" as const,
          metadata: {
            name: getAssetName(asset),
            assetType: getAssetType(asset),
            thumbnailUrl: getAssetThumbnail(asset) || "",
          },
        });
      }
    },
    [
      isAssetFavorited,
      addFavorite,
      removeFavorite,
      getAssetId,
      getAssetName,
      getAssetType,
      getAssetThumbnail,
    ]
  );

  return {
    favorites,
    isAssetFavorited,
    handleFavoriteToggle,
  };
}
