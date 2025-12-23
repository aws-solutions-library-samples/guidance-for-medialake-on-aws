// Response parser utilities for API responses
// Compatible with React Query and existing apiClient (Axios responses)
import { ApiKey, ApiKeyListResponse, ApiKeyResponse } from "../types/apiKey.types";

export const isValidApiKey = (apiKey: any): apiKey is ApiKey => {
  return (
    apiKey &&
    typeof apiKey === "object" && // pragma: allowlist secret
    typeof apiKey.id === "string" &&
    typeof apiKey.name === "string" &&
    (typeof apiKey.description === "string" ||
      apiKey.description === null ||
      apiKey.description === undefined) &&
    typeof apiKey.createdAt === "string" && // pragma: allowlist secret
    typeof apiKey.updatedAt === "string" &&
    typeof apiKey.isEnabled === "boolean" &&
    (apiKey.lastUsed === undefined ||
      apiKey.lastUsed === null ||
      typeof apiKey.lastUsed === "string")
  );
};

// Type guards for different response structures
export const isStringBody = (data: any): data is { body: string } => {
  return data && typeof data.body === "string";
};

export const isNestedBodyData = (data: any): data is { body: { data: any } } => {
  return data?.body && typeof data.body === "object" && data.body.data !== undefined;
};

export const isDirectData = (data: any): data is { status: string; data: any } => {
  return data?.status && data?.data !== undefined;
};

/**
 * Safely parse API keys list from various response formats
 * Returns empty array on parsing errors to maintain UI stability
 */
export const parseApiKeysList = (axiosResponseData: any): ApiKey[] => {
  try {
    // Handle string body format (older API format)
    if (isStringBody(axiosResponseData)) {
      const parsedBody = JSON.parse(axiosResponseData.body) as ApiKeyListResponse;
      if (parsedBody?.data?.apiKeys && Array.isArray(parsedBody.data.apiKeys)) {
        return parsedBody.data.apiKeys.filter(isValidApiKey);
      }
    }

    // Handle nested body.data.apiKeys format
    if (isNestedBodyData(axiosResponseData)) {
      const apiKeys = axiosResponseData.body.data.apiKeys;
      if (Array.isArray(apiKeys)) {
        return apiKeys.filter(isValidApiKey);
      }
    }

    // Handle direct response format {status, message, data: {apiKeys: []}}
    if (isDirectData(axiosResponseData)) {
      const apiKeys = axiosResponseData.data.apiKeys;
      if (Array.isArray(apiKeys)) {
        return apiKeys.filter(isValidApiKey);
      }
    }

    console.warn("Unexpected API response structure for API keys list:", axiosResponseData);
    return [];
  } catch (error) {
    console.error("Failed to parse API keys list response:", error);
    return [];
  }
};

/**
 * Safely parse single API key from various response formats
 * Throws error on parsing failure to trigger React Query error handling
 */
export const parseApiKey = (axiosResponseData: any): ApiKey => {
  try {
    // Handle string body format
    if (isStringBody(axiosResponseData)) {
      const parsedBody = JSON.parse(axiosResponseData.body) as ApiKeyResponse;
      if (parsedBody?.data && isValidApiKey(parsedBody.data)) {
        return parsedBody.data;
      }
    }

    // Handle nested body.data format
    if (isNestedBodyData(axiosResponseData)) {
      if (isValidApiKey(axiosResponseData.body.data)) {
        return axiosResponseData.body.data;
      }
    }

    // Handle direct response format {status, message, data: {...}}
    if (isDirectData(axiosResponseData)) {
      if (isValidApiKey(axiosResponseData.data)) {
        return axiosResponseData.data;
      }
    }

    throw new Error("Invalid API key response structure");
  } catch (error) {
    console.error("Failed to parse API key response:", error);
    throw new Error("Failed to parse API key response");
  }
};

/**
 * Parse generic response with string body (for mutations)
 * Handles both string body format and direct JSON format
 */
export const parseStringBodyResponse = <T>(axiosResponseData: any): T => {
  try {
    // Handle string body format (older API Gateway format)
    if (axiosResponseData?.body && typeof axiosResponseData.body === "string") {
      return JSON.parse(axiosResponseData.body);
    }

    // Handle direct JSON response format
    if (axiosResponseData?.status && axiosResponseData?.data !== undefined) {
      return axiosResponseData as T;
    }

    // If it's already the expected format, return it
    if (axiosResponseData) {
      return axiosResponseData as T;
    }

    throw new Error("Invalid response format");
  } catch (error) {
    console.error("Failed to parse string body response:", error);
    throw new Error("Failed to parse response body");
  }
};

/**
 * Handle 403 errors gracefully for API keys (return empty array instead of throwing)
 */
export const handleApiKeysError = (error: any): ApiKey[] => {
  if (error?.response?.status === 403) {
    console.log("API keys API returned 403 Forbidden - User likely does not have permission");
    return [];
  }
  // Re-throw other errors to maintain existing error handling
  throw error;
};
