import { QueryClient } from '@tanstack/react-query';

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: 3,
            staleTime: 0, // Always consider data stale
            gcTime: 1000 * 60 * 5, // Keep unused data in cache for 5 minutes
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
            refetchOnWindowFocus: true,
            refetchOnMount: 'always',
            refetchOnReconnect: true,
            throwOnError: false,
        },
    },
});
export default queryClient;
