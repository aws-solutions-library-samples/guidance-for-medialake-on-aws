import { apiClient } from "@/api/apiClient";
import { PIPELINES_API } from "./pipelines.endpoints";
import type {
  Pipeline,
  PipelinesResponse,
  CreatePipelineDto,
  UpdatePipelineDto,
  PipelineStatus,
  PipelineRun,
} from "../types/pipelines.types";

export class PipelinesService {
  static async getPipelines(): Promise<PipelinesResponse> {
    const response = await apiClient.get<PipelinesResponse>(
      PIPELINES_API.endpoints.GET_PIPELINES,
    );
    return response.data;
  }

  static async getPipeline(id: string): Promise<Pipeline> {
    const response = await apiClient.get<any>(
      PIPELINES_API.endpoints.GET_PIPELINE(id),
    );

    // Check if the response has the expected structure
    if (response.data && response.data.data && response.data.data.pipeline) {
      const pipelineData = response.data.data.pipeline;

      // Transform the pipeline data to match the expected structure
      // Extract name, description, and configuration from the definition property if it exists
      if (pipelineData.definition) {
        return {
          id: pipelineData.id,
          name: pipelineData.definition.name || pipelineData.name || "",
          description:
            pipelineData.definition.description ||
            pipelineData.description ||
            "",
          configuration: pipelineData.definition.configuration ||
            pipelineData.configuration || {
              nodes: [],
              edges: [],
              settings: {
                autoStart: false,
                retryAttempts: 3,
                timeout: 3600,
              },
            },
          type: pipelineData.type || "Custom",
          system: pipelineData.system || false,
          createdAt: pipelineData.createdAt || new Date().toISOString(),
          updatedAt: pipelineData.updatedAt || new Date().toISOString(),
          deploymentStatus: pipelineData.deploymentStatus,
          executionArn: pipelineData.executionArn,
        } as Pipeline;
      }

      // If definition doesn't exist, return the pipeline data as is
      return pipelineData as Pipeline;
    }

    // If the response doesn't have the expected structure, return the data as is
    return response.data;
  }

  static async createPipeline(data: CreatePipelineDto): Promise<{
    pipeline_id: string;
    execution_arn: string;
    status: string;
    pipeline_name: string;
    message: string;
  }> {
    const response = await apiClient.post<any>(
      PIPELINES_API.endpoints.CREATE_PIPELINE,
      data,
    );
    return response.data;
  }

  static async getPipelineStatus(executionArn: string): Promise<{
    execution_arn: string;
    step_function_status: string;
    step_function_output: any;
    pipeline: Pipeline | null;
  }> {
    const encodedArn = encodeURIComponent(executionArn);
    const response = await apiClient.get<any>(
      `/pipelines/status/${encodedArn}`,
    );
    return response.data;
  }

  static async updatePipeline(
    id: string,
    data: UpdatePipelineDto,
  ): Promise<Pipeline> {
    // For deployed pipelines, use the pipelines endpoint with pipeline_id
    if (data.updateDeployed) {
      // Create a new request object with the pipeline_id
      const updateData = {
        ...data,
        pipeline_id: id,
      };
      // Remove the updateDeployed flag as it's not needed by the backend
      delete updateData.updateDeployed;

      const response = await apiClient.post<any>(
        PIPELINES_API.endpoints.CREATE_PIPELINE,
        updateData,
      );
      return response.data;
    }

    // For non-deployed pipelines, use the existing update endpoint
    const response = await apiClient.put<Pipeline>(
      PIPELINES_API.endpoints.UPDATE_PIPELINE(id),
      data,
    );
    return response.data;
  }

  static async deletePipeline(id: string): Promise<void> {
    console.log(`[PipelinesService] Deleting pipeline with ID: ${id}`);
    console.log(
      `[PipelinesService] Using endpoint: ${PIPELINES_API.endpoints.DELETE_PIPELINE(id)}`,
    );

    // Simple, direct approach - let the controller handle timeouts and retries
    await apiClient.delete(PIPELINES_API.endpoints.DELETE_PIPELINE(id));
    console.log(
      `[PipelinesService] Delete request sent for pipeline ID: ${id}`,
    );
  }

  static async updateStatus(
    id: string,
    status: Partial<PipelineStatus>,
  ): Promise<Pipeline> {
    const response = await apiClient.patch<Pipeline>(
      PIPELINES_API.endpoints.UPDATE_STATUS(id),
      {
        status,
      },
    );
    return response.data;
  }

  static async getPipelineRuns(id: string): Promise<PipelineRun[]> {
    const response = await apiClient.get<PipelineRun[]>(
      PIPELINES_API.endpoints.GET_PIPELINE_RUNS(id),
    );
    return response.data;
  }

  static async startPipeline(id: string): Promise<void> {
    await apiClient.post(PIPELINES_API.endpoints.START_PIPELINE(id));
  }

  static async stopPipeline(id: string): Promise<void> {
    await apiClient.post(PIPELINES_API.endpoints.STOP_PIPELINE(id));
  }
}
