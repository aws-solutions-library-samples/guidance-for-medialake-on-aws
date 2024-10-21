import axios from 'axios';

const API_URL = '/api'; // Replace with your actual API URL

export const fetchPipelines = async () => {
    const response = await axios.get(`${API_URL}/pipelines`);
    return response.data;
};

export const createPipeline = async (newPipeline) => {
    const response = await axios.post(`${API_URL}/pipelines`, newPipeline);
    return response.data;
};

export const updatePipeline = async (updatedPipeline) => {
    const response = await axios.put(`${API_URL}/pipelines/${updatedPipeline.id}`, updatedPipeline);
    return response.data;
};

export const deletePipeline = async (pipelineId) => {
    const response = await axios.delete(`${API_URL}/pipelines/${pipelineId}`);
    return response.data;
};

