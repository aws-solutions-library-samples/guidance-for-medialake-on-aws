import { useCallback } from "react";
import { useFeatureFlag } from "../utils/featureFlags";
import {
  useGetFavorites,
  useAddFavorite,
  useRemoveFavorite,
} from "../api/hooks/useFavorites";

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
  // Check if favorites feature is enabled
  const favoritesFeature = useFeatureFlag("user-favorites-enabled", false);

  // Favorites functionality
  const { data: favorites } = useGetFavorites("ASSET");
  const { mutate: addFavorite } = useAddFavorite();
  const { mutate: removeFavorite } = useRemoveFavorite();

  // Check if an asset is favorited - only if feature is enabled
  const isAssetFavorited = useCallback(
    (assetId: string) => {
      if (!favoritesFeature.value || !favorites) return false;
      return favorites.some((favorite) => favorite.itemId === assetId);
    },
    [favorites, favoritesFeature.value],
  );

  // Handle favorite toggle - only if feature is enabled
  const handleFavoriteToggle = useCallback(
    (asset: T, event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();

      // If feature is disabled, do nothing
      if (!favoritesFeature.value) {
        console.log("Favorites feature is disabled");
        return;
      }

      const assetId = getAssetId(asset);

      console.log("Toggling favorite for asset:", assetId);
      console.log("Current favorites state:", favorites);

      if (isAssetFavorited(assetId)) {
        console.log("Removing favorite for asset:", assetId);
        removeFavorite({ itemType: "ASSET", itemId: assetId });
      } else {
        console.log("Adding favorite for asset:", assetId);
        const favoriteData = {
          itemId: assetId,
          itemType: "ASSET" as const, // Use const assertion to fix type error
          metadata: {
            name: getAssetName(asset),
            assetType: getAssetType(asset), // Note: using assetType to match what Favorites.tsx expects
            thumbnailUrl: getAssetThumbnail(asset) || "",
          },
        };
        console.log("Favorite data being sent:", favoriteData);
        addFavorite(favoriteData);
      }
    },
    [
      isAssetFavorited,
      addFavorite,
      removeFavorite,
      favorites,
      getAssetId,
      getAssetName,
      getAssetType,
      getAssetThumbnail,
      favoritesFeature.value,
    ],
  );

  return {
    favorites,
    isAssetFavorited,
    handleFavoriteToggle,
  };
}
