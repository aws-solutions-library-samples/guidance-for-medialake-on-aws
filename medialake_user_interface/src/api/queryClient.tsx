import { QueryClient } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't retry on 403 errors
      retry: (failureCount, error: any) => {
        // Don't retry on 403 Forbidden errors
        if (error?.response?.status === 403) {
          console.log("Not retrying 403 error:", error);
          return false;
        }
        // Otherwise retry up to 3 times
        return failureCount < 3;
      },
      staleTime: 1000 * 60 * 10, // Consider data fresh for 10 minutes (increased from 5)
      gcTime: 1000 * 60 * 30, // Keep unused data in cache for 30 minutes (increased from 10)
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false, // Don't refetch on window focus
      refetchOnMount: false, // Don't refetch on mount - rely on staleTime
      refetchOnReconnect: false, // Don't refetch on reconnect
      throwOnError: false,
    },
  },
});
export default queryClient;
