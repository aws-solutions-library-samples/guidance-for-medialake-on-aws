import { apiClient } from '@/api/apiClient';
import { PIPELINES_API } from './pipelines.endpoints';
import type {
    Pipeline,
    PipelinesResponse,
    CreatePipelineDto,
    UpdatePipelineDto,
    PipelineStatus,
    PipelineRun
} from '../types/pipelines.types';

export class PipelinesService {
    static async getPipelines(): Promise<PipelinesResponse> {
        const response = await apiClient.get<PipelinesResponse>(PIPELINES_API.endpoints.GET_PIPELINES);
        return response.data;
    }

    static async getPipeline(id: string): Promise<Pipeline> {
        const response = await apiClient.get<Pipeline>(PIPELINES_API.endpoints.GET_PIPELINE(id));
        return response.data;
    }

    static async createPipeline(data: CreatePipelineDto): Promise<Pipeline> {
        const response = await apiClient.post<Pipeline>(PIPELINES_API.endpoints.CREATE_PIPELINE, data);
        return response.data;
    }

    static async updatePipeline(id: string, data: UpdatePipelineDto): Promise<Pipeline> {
        const response = await apiClient.put<Pipeline>(PIPELINES_API.endpoints.UPDATE_PIPELINE(id), data);
        return response.data;
    }

    static async deletePipeline(id: string): Promise<void> {
        console.log(`[PipelinesService] Deleting pipeline with ID: ${id}`);
        console.log(`[PipelinesService] Using endpoint: ${PIPELINES_API.endpoints.DELETE_PIPELINE(id)}`);

        // Simple, direct approach - let the controller handle timeouts and retries
        await apiClient.delete(PIPELINES_API.endpoints.DELETE_PIPELINE(id));
        console.log(`[PipelinesService] Delete request sent for pipeline ID: ${id}`);
    }

    static async updateStatus(id: string, status: Partial<PipelineStatus>): Promise<Pipeline> {
        const response = await apiClient.patch<Pipeline>(PIPELINES_API.endpoints.UPDATE_STATUS(id), { status });
        return response.data;
    }

    static async getPipelineRuns(id: string): Promise<PipelineRun[]> {
        const response = await apiClient.get<PipelineRun[]>(PIPELINES_API.endpoints.GET_PIPELINE_RUNS(id));
        return response.data;
    }

    static async startPipeline(id: string): Promise<void> {
        await apiClient.post(PIPELINES_API.endpoints.START_PIPELINE(id));
    }

    static async stopPipeline(id: string): Promise<void> {
        await apiClient.post(PIPELINES_API.endpoints.STOP_PIPELINE(id));
    }
}
