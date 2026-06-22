import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";

export interface MyAssetsConnector {
  id: string;
  name: string;
  type: string;
  storageIdentifier: string;
  objectPrefix: string;
  status: string;
  region: string;
}

interface MyAssetsConnectorResponse {
  status: string;
  message: string;
  data: {
    connector: MyAssetsConnector;
  };
}

export const useMyAssetsConnector = () => {
  const { data, isLoading, error } = useQuery<MyAssetsConnectorResponse | null, Error>({
    queryKey: QUERY_KEYS.CONNECTORS.myAssets(),
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<MyAssetsConnectorResponse>(
          API_ENDPOINTS.MY_ASSETS_CONNECTOR,
          { signal, skipAccessDeniedRedirect: true } as any
        );
        return response.data;
      } catch (error: any) {
        logger.warn("Failed to fetch my-assets connector:", error?.message);
        return null;
      }
    },
    staleTime: Infinity,
  });

  return {
    connector: data?.data?.connector ?? null,
    isLoading,
    error,
  };
};
