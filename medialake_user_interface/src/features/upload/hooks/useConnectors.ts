import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { Connector } from "../types/upload.types";

interface ConnectorsResponse {
  status: string;
  data?: {
    connectors: Connector[];
  };
}

/**
 * Hook to fetch S3 connectors
 */
const useConnectors = () => {
  const fetchConnectors = useCallback(async (): Promise<Connector[]> => {
    try {
      const response = await apiClient.get<ConnectorsResponse>(
        API_ENDPOINTS.CONNECTORS,
      );

      if (response.data.status === "200" && response.data.data?.connectors) {
        // Filter only S3 connectors that are active
        return response.data.data.connectors.filter(
          (connector: Connector) =>
            connector.type === "s3" && connector.status === "active",
        );
      }

      return [];
    } catch (error) {
      console.error("Error fetching connectors:", error);
      throw error;
    }
  }, []);

  const {
    data: connectors = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["connectors", "s3"],
    queryFn: fetchConnectors,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  return {
    connectors,
    isLoading,
    error,
    refetch,
  };
};

export default useConnectors;
