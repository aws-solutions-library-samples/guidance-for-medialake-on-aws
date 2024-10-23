import axios from 'axios';

const API_URL = '/api'; // Replace with your actual API URL

export const fetchTags = async () => {
    const response = await axios.get(`${API_URL}/tags`);
    return response.data;
};

export const fetchTagGroups = async () => {
    const response = await axios.get(`${API_URL}/tag-groups`);
    return response.data;
};

export const createTag = async (newTag) => {
    const response = await axios.post(`${API_URL}/tags`, newTag);
    return response.data;
};

export const updateTag = async (updatedTag) => {
    const response = await axios.put(`${API_URL}/tags/${updatedTag.id}`, updatedTag);
    return response.data;
};

export const deleteTag = async (tagId) => {
    const response = await axios.delete(`${API_URL}/tags/${tagId}`);
    return response.data;
};

export const createTagGroup = async (newTagGroup) => {
    const response = await axios.post(`${API_URL}/tag-groups`, newTagGroup);
    return response.data;
};

export const updateTagGroup = async (updatedTagGroup) => {
    const response = await axios.put(`${API_URL}/tag-groups/${updatedTagGroup.id}`, updatedTagGroup);
    return response.data;
};

export const deleteTagGroup = async (tagGroupId) => {
    const response = await axios.delete(`${API_URL}/tag-groups/${tagGroupId}`);
    return response.data;
};

