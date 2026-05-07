import { QueryClient } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't retry on 403 errors
      retry: (failureCount, error: any) => {
        if (error?.response?.status === 403) {
          return false;
        }
        return failureCount < 3;
      },
      staleTime: 1000 * 60 * 2, // 2 minutes — reasonable default, override per-query as needed
      gcTime: 1000 * 60 * 10, // 10 minutes garbage collection
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      throwOnError: false,
    },
  },
});
export default queryClient;
