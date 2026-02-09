import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSnackbar } from "notistack";
import { useTranslation } from "react-i18next";
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

      const { data } = await apiClient.get(url);

      // Handle null or undefined response
      if (!data) {
        return [];
      }

      // Handle API Gateway response where body is a JSON string
      if (typeof data === "object" && "body" in data && typeof data.body === "string") {
        try {
          const parsed = JSON.parse(data.body);
          return parsed?.data?.favorites ?? [];
        } catch {
          return [];
        }
      }

      // Handle direct response structure with data.favorites
      if (typeof data === "object" && "data" in data) {
        const response = data as FavoritesResponse;
        return response?.data?.favorites ?? [];
      }

      // Handle case where data is already the favorites array
      if (Array.isArray(data)) {
        return data;
      }

      // Fallback to empty array
      return [];
    },
    staleTime: Infinity,
    gcTime: 1000 * 60 * 30,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
  });
};

// Context type for optimistic updates
interface MutationContext {
  previousFavorites: Favorite[] | undefined;
}

/**
 * Hook to add a favorite
 */
export const useAddFavorite = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<Favorite, Error, AddFavoriteRequest, MutationContext>({
    mutationFn: async (favoriteData) => {
      const response = await apiClient.post<AddFavoriteResponse>(
        API_ENDPOINTS.FAVORITES.BASE,
        favoriteData
      );

      // Handle different response structures
      const data = response.data;
      if (data.data?.favorite) {
        return data.data.favorite;
      } else if ((data as any).favorite) {
        return (data as any).favorite;
      } else if (data.data && !data.data.favorite) {
        return data.data as unknown as Favorite;
      }

      // Fallback: construct from request data
      return {
        itemId: favoriteData.itemId,
        itemType: favoriteData.itemType,
        metadata: favoriteData.metadata,
        addedAt: new Date().toISOString(),
      };
    },
    onMutate: async (newFavorite) => {
      const queryKey = QUERY_KEYS.FAVORITES.list(newFavorite.itemType);

      await queryClient.cancelQueries({ queryKey });
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.FAVORITES.all });

      const previousFavorites = queryClient.getQueryData<Favorite[]>(queryKey);

      queryClient.setQueryData<Favorite[]>(queryKey, (old) => {
        if (old?.some((fav) => fav.itemId === newFavorite.itemId)) {
          return old;
        }
        const optimisticFavorite: Favorite = {
          itemId: newFavorite.itemId,
          itemType: newFavorite.itemType,
          metadata: newFavorite.metadata,
          addedAt: new Date().toISOString(),
        };
        return old ? [...old, optimisticFavorite] : [optimisticFavorite];
      });

      return { previousFavorites };
    },
    onSuccess: (newFavorite, variables) => {
      const queryKey = QUERY_KEYS.FAVORITES.list(variables.itemType);
      const currentCache = queryClient.getQueryData<Favorite[]>(queryKey);

      if (!currentCache?.some((fav) => fav.itemId === newFavorite.itemId)) {
        queryClient.setQueryData<Favorite[]>(queryKey, (old) => {
          return old ? [...old, newFavorite] : [newFavorite];
        });
      } else {
        queryClient.setQueryData<Favorite[]>(queryKey, (old) => {
          if (!old) return [newFavorite];
          return old.map((fav) => (fav.itemId === newFavorite.itemId ? newFavorite : fav));
        });
      }
    },
    onError: (_, variables, context) => {
      if (context?.previousFavorites) {
        queryClient.setQueryData(
          QUERY_KEYS.FAVORITES.list(variables.itemType),
          context.previousFavorites
        );
      }
      enqueueSnackbar(t("favorites.errorAdding"), {
        variant: "error",
        autoHideDuration: 5000,
      });
    },
  });
};

/**
 * Hook to remove a favorite
 */
export const useRemoveFavorite = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<void, Error, { itemType: string; itemId: string }, MutationContext>({
    mutationFn: async ({ itemType, itemId }) => {
      await apiClient.delete(API_ENDPOINTS.FAVORITES.DELETE(itemType, itemId));
    },
    onMutate: async ({ itemType, itemId }) => {
      const queryKey = QUERY_KEYS.FAVORITES.list(itemType);

      await queryClient.cancelQueries({ queryKey });
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.FAVORITES.all });

      const previousFavorites = queryClient.getQueryData<Favorite[]>(queryKey);

      queryClient.setQueryData<Favorite[]>(queryKey, (old) => {
        return old?.filter((fav) => fav.itemId !== itemId) ?? [];
      });

      return { previousFavorites };
    },
    onSuccess: (_, variables) => {
      const queryKey = QUERY_KEYS.FAVORITES.list(variables.itemType);
      const currentCache = queryClient.getQueryData<Favorite[]>(queryKey);

      if (currentCache?.some((fav) => fav.itemId === variables.itemId)) {
        queryClient.setQueryData<Favorite[]>(
          queryKey,
          (old) => old?.filter((fav) => fav.itemId !== variables.itemId) ?? []
        );
      }
    },
    onError: (_, variables, context) => {
      if (context?.previousFavorites) {
        queryClient.setQueryData(
          QUERY_KEYS.FAVORITES.list(variables.itemType),
          context.previousFavorites
        );
      }
      enqueueSnackbar(t("favorites.errorRemoving"), {
        variant: "error",
        autoHideDuration: 5000,
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

  const isFavorited = favorites?.some((fav) => fav.itemId === itemId) || false;

  return {
    isFavorited,
    isLoading,
  };
};
