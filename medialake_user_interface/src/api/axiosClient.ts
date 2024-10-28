import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { authService } from './authService';
import { StorageHelper } from '../common/helpers/storage-helper';
import { isTokenExpiringSoon } from '../common/helpers/token-helper';

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

// Function to add callbacks to refreshSubscribers
const subscribeTokenRefresh = (cb: (token: string) => void) => {
    refreshSubscribers.push(cb);
};

// Function to execute all subscribers
const onTokenRefreshed = (token: string) => {
    refreshSubscribers.forEach(cb => cb(token));
    refreshSubscribers = [];
};

// Get the API endpoint from AWS configuration
const getBaseURL = () => {
    const awsConfig = StorageHelper.getAwsConfig();
    return awsConfig?.API?.REST?.RestApi?.endpoint || '';
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
            let token = authService.getToken();
            if (token && isTokenExpiringSoon(token)) {
                console.log('Token is expiring soon, refreshing...');
                token = await authService.refreshToken();
                if (!token) {
                    throw new Error('Failed to refresh token');
                }
            }
            if (token) {
                config.headers['Authorization'] = `Bearer ${token}`;
                console.log('Request with token:', token.substring(0, 20) + '...');
            }
            return config;
        } catch (error) {
            console.error('Error setting auth token:', error);
            authService.clearTokens();
            window.location.href = '/';
            return Promise.reject(error);
        }
    },
    (error) => Promise.reject(error)
);

// Add a response interceptor for token refresh
axiosClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        console.log('Response error:', error.response?.status, error.response?.data);

        const originalRequest = error.config;
        const isTokenExpired =
            (error.response?.status === 401 && error.response?.data?.message === "The incoming token has expired") ||
            error.response?.data?.message?.toLowerCase().includes('expired');

        console.log('Is token expired?', isTokenExpired);
        console.log('Original request retry status:', originalRequest._retry);

        // If token is expired and we haven't retried yet
        if (isTokenExpired && !originalRequest._retry) {
            originalRequest._retry = true;

            if (!isRefreshing) {
                console.log('Starting token refresh...');
                isRefreshing = true;

                try {
                    const newToken = await authService.refreshToken();
                    console.log('Token refresh successful');

                    if (newToken) {
                        // Update the authorization header with new token
                        originalRequest.headers.Authorization = `Bearer ${newToken}`;
                        // Notify all subscribers about the new token
                        onTokenRefreshed(newToken);
                        isRefreshing = false;

                        // Retry the original request with new token
                        return axiosClient(originalRequest);
                    }
                } catch (refreshError) {
                    console.error('Token refresh failed:', refreshError);
                    isRefreshing = false;
                    authService.clearTokens();
                    window.location.href = '/';
                    return Promise.reject(refreshError);
                }
            } else {
                // If refresh is already in progress, wait for the new token
                return new Promise(resolve => {
                    subscribeTokenRefresh(token => {
                        originalRequest.headers.Authorization = `Bearer ${token}`;
                        resolve(axiosClient(originalRequest));
                    });
                });
            }
        }

        return Promise.reject(error);
    }
);

export default axiosClient;
