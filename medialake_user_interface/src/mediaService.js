// mediaService.js
import axios from 'axios';

export const fetchVideos = async () => {
    const response = await axios.get('/api/videos');
    return response.data;
};

export const fetchImages = async () => {
    const response = await axios.get('/api/images');
    return response.data;
};

export const fetchAudios = async () => {
    const response = await axios.get('/api/audios');
    return response.data;
};
