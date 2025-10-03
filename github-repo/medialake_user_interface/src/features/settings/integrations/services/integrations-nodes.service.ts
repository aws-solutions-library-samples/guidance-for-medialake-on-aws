import {
  useGetNodes,
  useGetNode,
  useGetUnconfiguredNodeMethods,
} from "@/shared/nodes/api/nodesController";
import { Node, NodesError } from "@/shared/nodes/types/nodes.types";

export class IntegrationsNodesService {
  public static useNodes() {
    const {
      data,
      isLoading,
      error,
      isError,
      isFetching,
      refetch,
      isRefetching,
    } = useGetUnconfiguredNodeMethods();

    return {
      nodes: data?.data ?? [],
      isLoading,
      isFetching,
      isRefetching,
      error: error
        ? {
            status: (error as any).status || "error",
            message: error.message || "An unknown error occurred",
          }
        : null,
      hasError: isError,
      isEmpty: !data?.data?.length,
      refetch,
    };
  }

  public static useNode(nodeId: string) {
    const {
      data,
      isLoading,
      error,
      isError,
      isFetching,
      refetch,
      isRefetching,
    } = useGetNode(nodeId);

    return {
      node: data?.data?.[0],
      isLoading,
      isFetching,
      isRefetching,
      error: error
        ? {
            status: (error as any).status || "error",
            message: error.message || "An unknown error occurred",
          }
        : null,
      hasError: isError,
      isEmpty: !data?.data?.[0],
      refetch,
    };
  }

  public static getNodeById(nodes: Node[], nodeId: string): Node | undefined {
    return nodes.find((node) => node.nodeId === nodeId);
  }
}
