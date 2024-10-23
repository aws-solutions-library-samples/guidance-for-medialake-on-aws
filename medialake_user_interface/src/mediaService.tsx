// mediaService.js
import axios from 'axios';

export const fetchVideos = async (): Promise<any> => {
    const response = await axios.get('/api/videos');
    return response.data;
};

export const fetchImages = async (): Promise<any> => {
    const response = await axios.get('/api/images');
    return response.data;
};

export const fetchAudios = async (): Promise<any> => {
    const response = await axios.get('/api/audios');
    return response.data;
};
