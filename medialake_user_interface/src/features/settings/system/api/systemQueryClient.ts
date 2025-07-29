import { QueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/queryKeys";

// Query key constants
export const SYSTEM_QUERY_KEYS = {
  SYSTEM_SETTINGS: "systemSettings",
  SEARCH_PROVIDER: "searchProvider",
};

export const invalidateSystemQueries = (queryClient: QueryClient) => {
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.SYSTEM_SETTINGS.all });
  queryClient.invalidateQueries({
    queryKey: QUERY_KEYS.SYSTEM_SETTINGS.search(),
  });
};
