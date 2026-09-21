import { useCallback, useState } from "react";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import {
  CreateUploadRequest,
  CreateUploadResponse,
  SignMultipartRequest,
  SignMultipartResponse,
} from "../types/upload.types";

interface ApiEnvelope<T> {
  status: string;
  message: string;
  data: T;
}

interface UseS3UploadReturn {
  /** Sign the request that creates the object (PUT or CreateMultipartUpload). */
  createUpload: (request: CreateUploadRequest) => Promise<CreateUploadResponse>;
  /** Sign one request of an in-flight multipart upload (part, list, complete, abort). */
  signMultipart: (request: SignMultipartRequest) => Promise<SignMultipartResponse>;
  isLoading: boolean;
  error: Error | null;
}

/**
 * The two server calls behind Uppy's `signRequest`.
 *
 * The browser performs every S3 request itself against presigned URLs; the server only
 * presigns (and records the collection directives at create time). See
 * `assets/docs/uppy-6-upgrade.md`.
 */
const useS3Upload = (): UseS3UploadReturn => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const createUpload = useCallback(
    async (request: CreateUploadRequest): Promise<CreateUploadResponse> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.post<ApiEnvelope<CreateUploadResponse>>(
          API_ENDPOINTS.ASSETS.UPLOAD,
          request
        );

        if (response.data.status === "success" && response.data.data) {
          return response.data.data;
        }

        throw new Error(response.data.message || "Failed to create upload");
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Unknown error occurred";
        const error = new Error(`Error creating upload: ${errorMessage}`);
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const signMultipart = useCallback(
    async (request: SignMultipartRequest): Promise<SignMultipartResponse> => {
      // No loading state for individual signs to avoid UI flicker. Retry transient
      // failures (network blips, 429/502/503/504) with backoff — this is the hottest path
      // during large uploads, one call per part.
      const MAX_RETRIES = 3;
      const label =
        request.operation === "part"
          ? `part ${request.part_number}`
          : `${request.operation} for ${request.key}`;
      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          const response = await apiClient.post<ApiEnvelope<SignMultipartResponse>>(
            `${API_ENDPOINTS.ASSETS.UPLOAD}/multipart/sign`,
            request
          );

          if (response.data.status === "success" && response.data.data) {
            return response.data.data;
          }

          throw new Error(response.data.message || `Failed to sign ${label}`);
        } catch (err: any) {
          const status = err?.response?.status;
          const isRetryable =
            !status || status === 429 || status === 502 || status === 503 || status === 504;

          if (isRetryable && attempt < MAX_RETRIES) {
            // Exponential backoff with jitter to avoid thundering herd
            const baseDelay = 500 * Math.pow(2, attempt);
            const jitter = baseDelay * (0.5 + Math.random() * 0.5); // 50-100% of base
            await new Promise((r) => setTimeout(r, jitter));
            continue;
          }

          const errorMessage = err instanceof Error ? err.message : "Unknown error occurred";
          throw new Error(`Error signing ${label}: ${errorMessage}`);
        }
      }
      // Unreachable, but TypeScript needs it
      throw new Error(`Error signing ${label}: max retries exceeded`);
    },
    []
  );

  return {
    createUpload,
    signMultipart,
    isLoading,
    error,
  };
};

export default useS3Upload;
