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
      timeout: 120000, // 2 minutes — generous for sign/complete calls under heavy upload load
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
        // Proactively refresh the token if it's expiring within 60 seconds
        // so we never send an almost-expired token to the API
        const currentToken = StorageHelper.getToken();
        if (currentToken) {
          const { isTokenExpiringSoon } = await import("@/common/helpers/token-helper");
          if (isTokenExpiringSoon(currentToken, 60)) {
            try {
              const newToken = await authService.refreshToken();
              if (newToken) {
              }
            } catch (e) {
              console.warn("⚠️ Proactive token refresh failed, using current token", e);
            }
          }
        }

        const headers = await this.getHeaders();
        config.headers = {
          ...config.headers,
          ...headers,
        } as AxiosRequestHeaders;

        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    this.axiosInstance.interceptors.response.use(
      (response) => {
        // Check if response is HTML (CloudFront returning index.html for non-existent routes)
        const isHtmlResponse =
          typeof response.data === "string" && response.data.includes("<!DOCTYPE html>");

        if (isHtmlResponse) {
          // Return response as-is, let the calling code handle it
          return response;
        }

        // Unwrap Lambda proxy integration response format
        // API returns: {statusCode, body: ...}
        // We need: {success, data}
        if (
          response.data &&
          typeof response.data === "object" &&
          "body" in response.data &&
          "statusCode" in response.data
        ) {
          const body = response.data.body;
          if (typeof body === "object") {
            response.data = body;
          } else if (typeof body === "string") {
            try {
              response.data = JSON.parse(body);
            } catch {
              // Leave response.data as-is if body isn't valid JSON
            }
          }
        }

        return response;
      },
      async (error) => {
        const originalRequest = error.config;

        // Handle 401 Unauthorized (expired token from API Gateway UNAUTHORIZED response)
        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
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
              this.processQueue(new Error("Failed to refresh token"));
              return Promise.reject(error);
            }

            // Update the failed request with new token
            originalRequest.headers["Authorization"] = `Bearer ${newToken}`;

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

        // Handle 403 Forbidden errors from API Gateway (not S3)
        // API Gateway returns JSON, S3 returns XML
        // We need to check this before CloudFront converts the error
        if (error.response?.status === 403) {
          const contentType = error.response?.headers?.["content-type"] || "";
          const isApiError =
            contentType.includes("application/json") ||
            error.response?.data?.authError ||
            error.response?.data?.message;

          // Only redirect if this is an API authorization error, not an S3 error
          // Skip redirect if the request opted out via skipAccessDeniedRedirect
          if (isApiError) {
            // Before redirecting to access-denied, check if the local token is
            // expired. If so, this 403 is likely a stale-token issue rather than
            // a genuine permission denial — attempt a refresh first.
            if (!originalRequest._retry) {
              const { isTokenExpiringSoon } = await import("@/common/helpers/token-helper");
              const token = StorageHelper.getToken();
              if (token && isTokenExpiringSoon(token, 30)) {
                originalRequest._retry = true;

                // Use the same isRefreshing guard as the 401 handler to avoid
                // duplicate concurrent refresh calls
                if (this.isRefreshing) {
                  return new Promise((resolve, reject) => {
                    this.failedQueue.push({ resolve, reject });
                  })
                    .then(() => {
                      return this.axiosInstance(originalRequest);
                    })
                    .catch((err) => Promise.reject(err));
                }

                this.isRefreshing = true;

                try {
                  const newToken = await authService.refreshToken();
                  if (newToken) {
                    originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
                    this.processQueue();
                    return this.axiosInstance(originalRequest);
                  } else {
                    this.processQueue(new Error("Failed to refresh token"));
                  }
                } catch (refreshError) {
                  this.processQueue(refreshError);
                } finally {
                  this.isRefreshing = false;
                }
              }
            }

            const skipRedirect = originalRequest?.skipAccessDeniedRedirect === true;

            if (skipRedirect) {
              return Promise.reject(error);
            }

            // Extract error details from response
            const authError =
              error.response?.data?.authError ||
              error.response?.data?.message ||
              "You don't have permission to perform this action";
            const requiredPermission = error.response?.data?.requiredPermission;

            // Use dynamic import to avoid circular dependency issues
            import("@/utils/navigation").then(({ navigateToAccessDenied }) => {
              navigateToAccessDenied({
                message: authError,
                requiredPermission,
                attemptedUrl: error.config?.url,
                timestamp: new Date().toISOString(),
              });
            });

            // Still reject the promise so calling code can handle it if needed
            return Promise.reject(error);
          } else {
            // Let S3 403 errors pass through - CloudFront will convert to index.html
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
