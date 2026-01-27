import { StorageHelper } from "@/common/helpers/storage-helper";
import axios, { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";

class PublicApiClient {
  private axiosInstance: AxiosInstance | null = null;

  private getBaseURL() {
    const awsConfig = StorageHelper.getAwsConfig();
    const baseURL = awsConfig?.API?.REST?.RestApi?.endpoint || "";
    console.log("🌐 Base URL Configuration:", {
      hasConfig: !!awsConfig,
      hasAPI: !!awsConfig?.API,
      hasREST: !!awsConfig?.API?.REST,
      hasRestApi: !!awsConfig?.API?.REST?.RestApi,
      endpoint: baseURL,
      fullConfig: awsConfig,
    });
    return baseURL;
  }

  // Lazily initialize axios instance on first use - prevent missing AWS config at module load time
  private getAxiosInstance(): AxiosInstance {
    if (!this.axiosInstance) {
      this.axiosInstance = axios.create({
        baseURL: this.getBaseURL(),
        headers: {
          "Cache-Control": "no-cache, no-store, must-revalidate",
          Pragma: "no-cache",
          Expires: "0",
        },
      });
      this.setupInterceptors();
    }
    return this.axiosInstance;
  }

  private setupInterceptors() {
    this.axiosInstance.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        console.log("🚀 Public API Request:", {
          method: config.method?.toUpperCase(),
          url: config.url,
          baseURL: config.baseURL,
          fullURL: `${config.baseURL}${config.url}`,
        });
        return config;
      },
      (error) => {
        console.error("❌ Public Request Interceptor Error:", error);
        return Promise.reject(error);
      }
    );

    this.axiosInstance.interceptors.response.use(
      (response) => {
        console.log("✅ Public API Response Success:", {
          status: response.status,
          url: response.config.url,
          method: response.config.method?.toUpperCase(),
        });
        return response;
      },
      (error) => {
        console.error("❌ Public API Response Error:", {
          status: error.response?.status,
          statusText: error.response?.statusText,
          url: error.config?.url,
          method: error.config?.method?.toUpperCase(),
          message: error.response?.data?.message || error.message,
        });
        return Promise.reject(error);
      }
    );
  }

  public get<T>(url: string, config?: AxiosRequestConfig) {
    return this.getAxiosInstance().get<T>(url, config);
  }

  public post<T>(url: string, data?: any, config?: AxiosRequestConfig) {
    return this.getAxiosInstance().post<T>(url, data, config);
  }

  public put<T>(url: string, data?: any, config?: AxiosRequestConfig) {
    return this.getAxiosInstance().put<T>(url, data, config);
  }

  public delete<T>(url: string, config?: AxiosRequestConfig) {
    return this.getAxiosInstance().delete<T>(url, config);
  }

  public patch<T>(url: string, data?: any, config?: AxiosRequestConfig) {
    return this.getAxiosInstance().patch<T>(url, data, config);
  }
}

export const publicApiClient = new PublicApiClient();
