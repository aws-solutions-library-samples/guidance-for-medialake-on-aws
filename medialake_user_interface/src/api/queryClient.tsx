import { QueryClient } from '@tanstack/react-query';

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: 3,
            staleTime: 0,
            gcTime: 0,
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
            refetchOnWindowFocus: true,
            refetchOnMount: true,
            refetchOnReconnect: true,
            throwOnError: false,
        },
    },
});
export default queryClient;
