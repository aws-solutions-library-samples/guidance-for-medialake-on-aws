import { useCallback, useState } from "react";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import {
  CompleteMultipartRequest,
  CompleteMultipartResponse,
  AbortMultipartRequest,
  SignPartRequest,
  SignPartResponse,
} from "../types/upload.types";

interface UploadRequest {
  connector_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  path?: string;
}

interface S3UploadResponse {
  bucket: string;
  key: string;
  presigned_post?: {
    url: string;
    fields: Record<string, string>;
  };
  upload_id?: string;
  part_urls?: Array<{
    part_number: number;
    presigned_url: string;
  }>;
  expires_in: number;
  multipart: boolean;
  part_size?: number;
  total_parts?: number;
}

interface UseS3UploadReturn {
  getPresignedUrl: (request: UploadRequest) => Promise<S3UploadResponse>;
  signPart: (request: SignPartRequest) => Promise<SignPartResponse>;
  completeMultipartUpload: (
    request: CompleteMultipartRequest,
  ) => Promise<CompleteMultipartResponse>;
  abortMultipartUpload: (request: AbortMultipartRequest) => Promise<void>;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook to get presigned URLs for S3 uploads
 */
const useS3Upload = (): UseS3UploadReturn => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const getPresignedUrl = useCallback(
    async (request: UploadRequest): Promise<S3UploadResponse> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.post<{
          status: string;
          message: string;
          data: S3UploadResponse;
        }>(API_ENDPOINTS.ASSETS.UPLOAD, request);

        if (response.data.status === "success" && response.data.data) {
          return response.data.data;
        }

        throw new Error(
          response.data.message || "Failed to generate presigned URL",
        );
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Unknown error occurred";
        const error = new Error(
          `Error generating presigned URL: ${errorMessage}`,
        );
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const completeMultipartUpload = useCallback(
    async (
      request: CompleteMultipartRequest,
    ): Promise<CompleteMultipartResponse> => {
      setIsLoading(true);
      setError(null);

      try {
        console.log("Completing multipart upload:", {
          upload_id: request.upload_id,
          key: request.key,
          parts: request.parts.length,
        });

        const response = await apiClient.post<{
          status: string;
          message: string;
          data: CompleteMultipartResponse;
        }>(`${API_ENDPOINTS.ASSETS.UPLOAD}/multipart/complete`, request);

        if (response.data.status === "success" && response.data.data) {
          return response.data.data;
        }

        throw new Error(
          response.data.message || "Failed to complete multipart upload",
        );
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Unknown error occurred";
        const error = new Error(
          `Error completing multipart upload for ${request.key}: ${errorMessage}`,
        );
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const signPart = useCallback(
    async (request: SignPartRequest): Promise<SignPartResponse> => {
      // Don't set loading state for individual part signing to avoid UI flickering
      try {
        const response = await apiClient.post<{
          status: string;
          message: string;
          data: SignPartResponse;
        }>(`${API_ENDPOINTS.ASSETS.UPLOAD}/multipart/sign`, request);

        if (response.data.status === "success" && response.data.data) {
          return response.data.data;
        }

        throw new Error(response.data.message || "Failed to sign part");
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Unknown error occurred";
        const error = new Error(
          `Error signing part ${request.part_number}: ${errorMessage}`,
        );
        throw error;
      }
    },
    [],
  );

  const abortMultipartUpload = useCallback(
    async (request: AbortMultipartRequest): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        console.log("Aborting multipart upload:", {
          upload_id: request.upload_id,
          key: request.key,
        });

        await apiClient.post<{
          status: string;
          message: string;
        }>(`${API_ENDPOINTS.ASSETS.UPLOAD}/multipart/abort`, request);

        // Success - no return value needed
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Unknown error occurred";
        const error = new Error(
          `Error aborting multipart upload for ${request.key}: ${errorMessage}`,
        );
        setError(error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  return {
    getPresignedUrl,
    signPart,
    completeMultipartUpload,
    abortMultipartUpload,
    isLoading,
    error,
  };
};

export default useS3Upload;
