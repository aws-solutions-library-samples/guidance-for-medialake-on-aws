import { QueryClient } from "@tanstack/react-query";

export const environmentsQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // Data stays fresh for 5 minutes
      gcTime: 1000 * 60 * 10, // Keep in cache for 10 minutes
      refetchOnWindowFocus: false,
      refetchOnMount: true,
      retry: 2,
    },
  },
});
