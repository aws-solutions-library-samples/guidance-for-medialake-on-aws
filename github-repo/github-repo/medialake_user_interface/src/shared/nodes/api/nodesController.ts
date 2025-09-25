import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { logger } from "@/common/helpers/logger";
import { useErrorModal } from "@/hooks/useErrorModal";
import { NodesResponse } from "../types/nodes.types";
import { NODES_API } from "./nodes.endpoints";

export const useGetNodes = () => {
  const { showError } = useErrorModal();

  return useQuery<NodesResponse>({
    queryKey: ["nodes"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<NodesResponse>(
          NODES_API.endpoints.GET_NODES,
          {
            signal,
          },
        );

        if (!response.data?.data) {
          throw new Error("Invalid nodes response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Nodes fetch error:", error);
        showError("Failed to fetch nodes");
        throw error;
      }
    },
  });
};

export const useGetNode = (nodeId: string, options?: { enabled?: boolean }) => {
  const { showError } = useErrorModal();

  return useQuery<NodesResponse>({
    queryKey: ["nodes", nodeId],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<NodesResponse>(
          NODES_API.endpoints.GET_NODE(nodeId),
          {
            signal,
          },
        );

        if (!response.data?.data) {
          throw new Error("Invalid node response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Node fetch error:", error);
        showError("Failed to fetch node");
        throw error;
      }
    },
    enabled: options?.enabled !== undefined ? options.enabled : !!nodeId,
  });
};

export const useGetUnconfiguredNodeMethods = () => {
  const { showError } = useErrorModal();

  return useQuery<NodesResponse>({
    queryKey: ["nodes", "unconfigured"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<NodesResponse>(
          NODES_API.endpoints.GET_UNCONFIGURED_METHODS,
          { signal },
        );

        if (!response.data?.data) {
          throw new Error("Invalid unconfigured methods response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Unconfigured methods fetch error:", error);
        showError("Failed to fetch unconfigured methods");
        throw error;
      }
    },
  });
};

export const useGetNodeMethods = (nodeId: string) => {
  const { showError } = useErrorModal();

  return useQuery<NodesResponse>({
    queryKey: ["nodes", nodeId, "methods"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<NodesResponse>(
          NODES_API.endpoints.GET_NODE_METHODS(nodeId),
          { signal },
        );

        if (!response.data?.data) {
          throw new Error("Invalid node methods response structure");
        }

        return response.data;
      } catch (error) {
        logger.error("Node methods fetch error:", error);
        showError("Failed to fetch node methods");
        throw error;
      }
    },
    enabled: !!nodeId,
  });
};
