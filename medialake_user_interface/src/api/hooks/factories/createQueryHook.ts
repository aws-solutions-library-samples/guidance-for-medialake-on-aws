import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { apiClient } from "../../apiClient";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import type { ApiResponse } from "../../types/api.types";

export const createQueryHook = <TData, TError = Error>(
  endpoint: string,
  queryKey: readonly unknown[],
) => {
  return (
    options?: Omit<
      UseQueryOptions<ApiResponse<TData>, TError>,
      "queryKey" | "queryFn"
    >,
  ) => {
    const { showError } = useErrorModal();

    return useQuery({
      queryKey,
      queryFn: async ({ signal }) => {
        try {
          const response = await apiClient.get<ApiResponse<TData>>(endpoint, {
            signal,
          });
          return response.data;
        } catch (error) {
          logger.error(`Query error for ${endpoint}:`, error);
          showError(`Failed to fetch data from ${endpoint}`);
          throw error;
        }
      },
      ...options,
    });
  };
};

export const createMutationHook = <TData, TVariables>(
  endpoint: string,
  queryKey: readonly unknown[],
) => {
  return (
    options?: UseMutationOptions<ApiResponse<TData>, Error, TVariables>,
  ) => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation({
      mutationFn: async (variables) => {
        try {
          const response = await apiClient.post<ApiResponse<TData>>(
            endpoint,
            variables,
          );
          return response.data;
        } catch (error) {
          logger.error(`Mutation error for ${endpoint}:`, error);
          showError(`Failed to update data at ${endpoint}`);
          throw error;
        }
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey });
      },
      ...options,
    });
  };
};
