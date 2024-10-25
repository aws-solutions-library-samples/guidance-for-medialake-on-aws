import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { authService } from './authService';
import { StorageHelper } from '../common/helpers/storage-helper';

// Get the API endpoint from AWS configuration
const getBaseURL = () => {
    const awsConfig = StorageHelper.getAwsConfig();
    const baseURL = awsConfig?.API?.REST?.RestApi?.endpoint + '/api' || '';
    console.log('Base URL:', baseURL);
    return baseURL;
};

const axiosClient: AxiosInstance = axios.create({
    baseURL: getBaseURL(),
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add a request interceptor
axiosClient.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
        try {
            const token = authService.getToken();
            if (token) {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
            return config;
        } catch (error) {
            console.error('Error setting auth token:', error);
            return Promise.reject(error);
        }
    },
    (error) => Promise.reject(error)
);

// Add a response interceptor for token refresh
axiosClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // If the error is 401 and we haven't tried to refresh the token yet
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                const newToken = await authService.refreshToken();
                if (newToken) {
                    // Update the failed request with the new token
                    originalRequest.headers.Authorization = `Bearer ${newToken}`;
                    return axiosClient(originalRequest);
                }
            } catch (refreshError) {
                // If refresh fails, clear tokens and redirect to login
                authService.clearTokens();
                window.location.href = '/';
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

export default axiosClient;
