import axios, { AxiosInstance, AxiosRequestConfig, AxiosRequestHeaders, InternalAxiosRequestConfig } from 'axios';
import { ApiClientBase } from './apiClientBase';
import { StorageHelper } from '../common/helpers/storage-helper';
import { authService } from './authService';

class ApiClient extends ApiClientBase {
    private axiosInstance: AxiosInstance;
    private isRefreshing = false;
    private failedQueue: Array<{
        resolve: (value?: unknown) => void;
        reject: (reason?: any) => void;
    }> = [];

    constructor() {
        super();
        this.axiosInstance = axios.create({
            baseURL: this.getBaseURL(),
        });
        this.setupInterceptors();
    }

    private getBaseURL() {
        const awsConfig = StorageHelper.getAwsConfig();
        return awsConfig?.API?.REST?.RestApi?.endpoint || '';
    }

    private processQueue(error: any = null) {
        this.failedQueue.forEach(promise => {
            if (error) {
                promise.reject(error);
            } else {
                promise.resolve();
            }
        });
        this.failedQueue = [];
    }

    private setupInterceptors() {
        this.axiosInstance.interceptors.request.use(
            async (config: InternalAxiosRequestConfig) => {
                const headers = await this.getHeaders();
                config.headers = {
                    ...config.headers,
                    ...headers,
                } as AxiosRequestHeaders;
                return config;
            },
            (error) => Promise.reject(error)
        );

        this.axiosInstance.interceptors.response.use(
            (response) => response,
            async (error) => {
                const originalRequest = error.config;

                // Check if error is token expiration
                if (error.response?.status === 401 &&
                    error.response?.data?.message === "The incoming token has expired" &&
                    !originalRequest._retry) {

                    if (this.isRefreshing) {
                        // If refresh is already in progress, queue this request
                        return new Promise((resolve, reject) => {
                            this.failedQueue.push({ resolve, reject });
                        })
                            .then(() => {
                                return this.axiosInstance(originalRequest);
                            })
                            .catch(err => Promise.reject(err));
                    }

                    originalRequest._retry = true;
                    this.isRefreshing = true;

                    try {
                        const newToken = await authService.refreshToken();
                        if (!newToken) {
                            this.processQueue(new Error('Failed to refresh token'));
                            return Promise.reject(error);
                        }

                        // Update the failed request with new token
                        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;

                        // Process any requests that were waiting
                        this.processQueue();

                        // Retry the original request
                        return this.axiosInstance(originalRequest);
                    } catch (refreshError) {
                        this.processQueue(refreshError);
                        return Promise.reject(refreshError);
                    } finally {
                        this.isRefreshing = false;
                    }
                }

                return Promise.reject(error);
            }
        );
    }

    public get<T>(url: string, config?: AxiosRequestConfig) {
        return this.axiosInstance.get<T>(url, config);
    }

    public post<T>(url: string, data?: any, config?: AxiosRequestConfig) {
        return this.axiosInstance.post<T>(url, data, config);
    }

    public put<T>(url: string, data?: any, config?: AxiosRequestConfig) {
        return this.axiosInstance.put<T>(url, data, config);
    }

    public delete<T>(url: string, config?: AxiosRequestConfig) {
        return this.axiosInstance.delete<T>(url, config);
    }

    public patch<T>(url: string, data?: any, config?: AxiosRequestConfig) {
        return this.axiosInstance.patch<T>(url, data, config);
    }
}

export const apiClient = new ApiClient();
