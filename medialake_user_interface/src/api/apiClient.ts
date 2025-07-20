import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosRequestHeaders,
  InternalAxiosRequestConfig,
} from "axios";
import { ApiClientBase } from "@/api/apiClientBase";
import { StorageHelper } from "@/common/helpers/storage-helper";
import { authService } from "@/api/authService";

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

      headers: {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        Pragma: "no-cache",
        Expires: "0",
      },
    });
    this.setupInterceptors();
  }

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

  private processQueue(error: any = null) {
    this.failedQueue.forEach((promise) => {
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
        console.log("🚀 API Request:", {
          method: config.method?.toUpperCase(),
          url: config.url,
          baseURL: config.baseURL,
          fullURL: `${config.baseURL}${config.url}`,
          hasAuthHeader: !!config.headers?.Authorization,
        });

        const headers = await this.getHeaders();
        config.headers = {
          ...config.headers,
          ...headers,
        } as AxiosRequestHeaders;

        console.log("🔑 Auth Header Added:", !!config.headers?.Authorization);
        return config;
      },
      (error) => {
        console.error("❌ Request Interceptor Error:", error);
        return Promise.reject(error);
      },
    );

    this.axiosInstance.interceptors.response.use(
      (response) => {
        console.log("✅ API Response Success:", {
          status: response.status,
          url: response.config.url,
          method: response.config.method?.toUpperCase(),
        });
        return response;
      },
      async (error) => {
        console.error("❌ API Response Error:", {
          status: error.response?.status,
          statusText: error.response?.statusText,
          url: error.config?.url,
          method: error.config?.method?.toUpperCase(),
          message: error.response?.data?.message || error.message,
          headers: error.response?.headers,
        });

        const originalRequest = error.config;

        // Check if error is token expiration
        if (
          error.response?.status === 401 &&
          error.response?.data?.message === "The incoming token has expired" &&
          !originalRequest._retry
        ) {
          console.log("🔄 Token expired, attempting refresh...");

          if (this.isRefreshing) {
            console.log(
              "⏳ Token refresh already in progress, queuing request...",
            );
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then(() => {
                return this.axiosInstance(originalRequest);
              })
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            const newToken = await authService.refreshToken();
            if (!newToken) {
              console.error("❌ Failed to refresh token");
              this.processQueue(new Error("Failed to refresh token"));
              return Promise.reject(error);
            }

            console.log("✅ Token refreshed successfully");
            // Update the failed request with new token
            originalRequest.headers["Authorization"] = `Bearer ${newToken}`;

            // Process any requests that were waiting
            this.processQueue();

            // Retry the original request
            return this.axiosInstance(originalRequest);
          } catch (refreshError) {
            console.error("❌ Token refresh failed:", refreshError);
            this.processQueue(refreshError);
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(error);
      },
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
