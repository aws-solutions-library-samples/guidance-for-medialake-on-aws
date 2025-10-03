import { useCallback, useState } from "react";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";

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

  return {
    getPresignedUrl,
    isLoading,
    error,
  };
};

export default useS3Upload;
