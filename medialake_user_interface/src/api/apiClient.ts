import axios, { AxiosInstance, AxiosRequestConfig, AxiosRequestHeaders, InternalAxiosRequestConfig } from 'axios';
import { ApiClientBase } from './apiClientBase';
import { StorageHelper } from '../common/helpers/storage-helper';

class ApiClient extends ApiClientBase {
    private axiosInstance: AxiosInstance;

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

        // Add your response interceptor for token refresh if needed
    }

    public get<T>(url: string, config?: AxiosRequestConfig) {
        return this.axiosInstance.get<T>(url, config);
    }

    // Add other HTTP methods (post, put, delete) as needed
}

export const apiClient = new ApiClient();
