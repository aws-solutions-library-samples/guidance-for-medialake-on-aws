import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";

// Types for favorites
export interface Favorite {
  itemId: string;
  itemType: "ASSET" | "PIPELINE" | "COLLECTION";
  metadata?: Record<string, any>;
  addedAt?: string;
}

export interface AddFavoriteRequest {
  itemId: string;
  itemType: "ASSET" | "PIPELINE" | "COLLECTION";
  metadata?: Record<string, any>;
}

interface FavoritesResponse {
  status: string;
  message: string;
  data: {
    favorites: Favorite[];
  };
}

interface AddFavoriteResponse {
  status: string;
  message: string;
  data: {
    favorite: Favorite;
  };
}

/**
 * Hook to fetch user favorites
 * @param itemType Optional filter for specific item types
 */
export const useGetFavorites = (itemType?: string) => {
  return useQuery<Favorite[], Error>({
    queryKey: QUERY_KEYS.FAVORITES.list(itemType),
    queryFn: async () => {
      const url = itemType
        ? `${API_ENDPOINTS.FAVORITES.BASE}?itemType=${itemType}`
        : API_ENDPOINTS.FAVORITES.BASE;

      const { data } = await apiClient.get<FavoritesResponse>(url);
      return data.data.favorites;
    },
  });
};

/**
 * Hook to add a favorite
 */
export const useAddFavorite = () => {
  const queryClient = useQueryClient();

  return useMutation<Favorite, Error, AddFavoriteRequest>({
    mutationFn: async (favoriteData) => {
      const { data } = await apiClient.post<AddFavoriteResponse>(
        API_ENDPOINTS.FAVORITES.BASE,
        favoriteData,
      );
      return data.data.favorite;
    },
    onSuccess: (data, variables) => {
      console.log("Adding favorite succeeded:", data);
      console.log("Invalidating queries with key:", QUERY_KEYS.FAVORITES.all);

      // Invalidate all favorites queries to refresh data
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.FAVORITES.all });

      // Also explicitly invalidate the specific query for the item type
      // This ensures that filtered queries like useGetFavorites('ASSET') are also refreshed
      console.log(
        "Invalidating specific query with itemType:",
        variables.itemType,
      );
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.FAVORITES.list(variables.itemType),
      });
    },
  });
};

/**
 * Hook to remove a favorite
 */
export const useRemoveFavorite = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { itemType: string; itemId: string }>({
    mutationFn: async ({ itemType, itemId }) => {
      await apiClient.delete(API_ENDPOINTS.FAVORITES.DELETE(itemType, itemId));
    },
    onSuccess: (_, variables) => {
      console.log("Removing favorite succeeded for:", variables);
      console.log("Invalidating queries with key:", QUERY_KEYS.FAVORITES.all);

      // Invalidate all favorites queries to refresh data
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.FAVORITES.all });

      // Also explicitly invalidate the specific query for the item type
      console.log(
        "Invalidating specific query with itemType:",
        variables.itemType,
      );
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.FAVORITES.list(variables.itemType),
      });
    },
  });
};

/**
 * Hook to check if an item is favorited
 * This is a helper hook that uses the useGetFavorites hook
 */
export const useIsFavorited = (itemId: string, itemType: string) => {
  const { data: favorites, isLoading } = useGetFavorites(itemType);

  const isFavorited =
    favorites?.some((favorite) => favorite.itemId === itemId) || false;

  return {
    isFavorited,
    isLoading,
  };
};
