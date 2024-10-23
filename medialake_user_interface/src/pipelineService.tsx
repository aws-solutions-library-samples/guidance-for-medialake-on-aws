import axios, { AxiosResponse } from 'axios';

const API_URL = '/api'; // Replace with your actual API URL

export interface Pipeline {
    id: string;
    // Add other properties as needed
}

export const fetchPipelines = async (): Promise<Pipeline[]> => {
    const response: AxiosResponse<Pipeline[]> = await axios.get(`${API_URL}/pipelines`);
    return response.data;
};

export const createPipeline = async (newPipeline: Omit<Pipeline, 'id'>): Promise<Pipeline> => {
    const response: AxiosResponse<Pipeline> = await axios.post(`${API_URL}/pipelines`, newPipeline);
    return response.data;
};

export const updatePipeline = async (updatedPipeline: Pipeline): Promise<Pipeline> => {
    const response: AxiosResponse<Pipeline> = await axios.put(`${API_URL}/pipelines/${updatedPipeline.id}`, updatedPipeline);
    return response.data;
};

export const deletePipeline = async (pipelineId: string): Promise<void> => {
    await axios.delete(`${API_URL}/pipelines/${pipelineId}`);
};
