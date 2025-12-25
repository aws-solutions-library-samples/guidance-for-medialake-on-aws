import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/queryKeys";

interface UseWidgetDataOptions {
  widgetId: string;
  queryKey?: readonly unknown[];
  onRefresh?: () => void;
  onError?: (error: Error) => void;
}

interface UseWidgetDataReturn {
  isRefreshing: boolean;
  lastRefreshed: Date | null;
  refresh: () => Promise<void>;
  invalidateCache: () => void;
}

/**
 * Hook for managing widget data operations
 * Provides refresh functionality and cache management
 */
export const useWidgetData = ({
  queryKey,
  onRefresh,
  onError,
}: UseWidgetDataOptions): UseWidgetDataReturn => {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  /**
   * Refresh widget data by invalidating the query cache
   */
  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      if (queryKey) {
        await queryClient.invalidateQueries({ queryKey });
      }

      if (onRefresh) {
        onRefresh();
      }

      setLastRefreshed(new Date());
    } catch (error) {
      if (onError && error instanceof Error) {
        onError(error);
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [queryClient, queryKey, onRefresh, onError]);

  /**
   * Invalidate cache without triggering loading state
   */
  const invalidateCache = useCallback(() => {
    if (queryKey) {
      queryClient.invalidateQueries({ queryKey });
    }
  }, [queryClient, queryKey]);

  return {
    isRefreshing,
    lastRefreshed,
    refresh,
    invalidateCache,
  };
};

/**
 * Pre-configured hook for Favorites widget data
 */
export const useFavoritesWidgetData = (widgetId: string) => {
  return useWidgetData({
    widgetId,
    queryKey: QUERY_KEYS.FAVORITES.all,
  });
};

/**
 * Pre-configured hook for Collections widget data
 */
export const useCollectionsWidgetData = (widgetId: string) => {
  return useWidgetData({
    widgetId,
    queryKey: QUERY_KEYS.COLLECTIONS.lists(),
  });
};

/**
 * Pre-configured hook for Recent Assets widget data
 */
export const useRecentAssetsWidgetData = (widgetId: string) => {
  return useWidgetData({
    widgetId,
    queryKey: QUERY_KEYS.SEARCH.all,
  });
};
