import { integrationsController } from "@/features/settings/integrations/api/integrations.controller";
import type { Integration } from "@/features/settings/integrations/types/integrations.types";
import type { PipelineNode } from "../types/pipelines.types";

export interface InvalidNodeInfo {
  nodeId: string;
  nodeLabel: string;
  invalidIntegrationId: string;
  nodeIndex: number;
}

export interface ValidationResult {
  isValid: boolean;
  invalidNodes: InvalidNodeInfo[];
  availableIntegrations: Integration[];
}

export interface IntegrationMapping {
  nodeIndex: number;
  oldIntegrationId: string;
  newIntegrationId: string;
}

export class IntegrationValidationService {
  static async validateIntegrationIds(
    nodes: PipelineNode[],
  ): Promise<ValidationResult> {
    try {
      // Fetch available integrations
      const integrationsResponse =
        await integrationsController.getIntegrations();
      const availableIntegrations = integrationsResponse.data || [];

      // Extract integration IDs from nodes
      const invalidNodes: InvalidNodeInfo[] = [];

      nodes.forEach((node, index) => {
        const integrationId = node.data?.configuration?.integrationId;

        if (integrationId && node.data?.type === "INTEGRATION") {
          // Check if integration ID exists in available integrations
          const integrationExists = availableIntegrations.some(
            (integration) => integration.id === integrationId,
          );

          if (!integrationExists) {
            invalidNodes.push({
              nodeId: node.id,
              nodeLabel: node.data.label,
              invalidIntegrationId: integrationId,
              nodeIndex: index,
            });
          }
        }
      });

      return {
        isValid: invalidNodes.length === 0,
        invalidNodes,
        availableIntegrations,
      };
    } catch (error) {
      console.error(
        "[IntegrationValidationService] Error validating integration IDs:",
        error,
      );
      throw error;
    }
  }

  static mapInvalidIntegrationIds(
    nodes: PipelineNode[],
    mappings: IntegrationMapping[],
  ): PipelineNode[] {
    return nodes.map((node, index) => {
      const mapping = mappings.find((m) => m.nodeIndex === index);

      if (
        mapping &&
        node.data?.configuration?.integrationId === mapping.oldIntegrationId
      ) {
        return {
          ...node,
          data: {
            ...node.data,
            configuration: {
              ...node.data.configuration,
              integrationId: mapping.newIntegrationId,
            },
          },
        };
      }

      return node;
    });
  }
}
