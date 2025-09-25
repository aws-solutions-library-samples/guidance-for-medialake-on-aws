import { apiClient } from "@/api/apiClient";
import { NodesResponse } from "../types/nodes.types";
import { NODES_API } from "./nodes.endpoints";

export class NodesService {
  public static async getNodes(): Promise<NodesResponse> {
    const response = await apiClient.get<NodesResponse>(
      NODES_API.endpoints.GET_NODES,
    );
    return response.data;
  }

  public static async getNode(nodeId: string): Promise<NodesResponse> {
    const response = await apiClient.get<NodesResponse>(
      NODES_API.endpoints.GET_NODE(nodeId),
    );
    return response.data;
  }
}
