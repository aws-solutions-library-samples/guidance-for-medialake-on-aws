import { useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import queryClient from "@/api/queryClient";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "../../common/helpers/logger";
import { useErrorModal } from "../../hooks/useErrorModal";
import type {
  S3BucketResponse,
  ConnectorResponse,
  CreateConnectorRequest,
  UpdateConnectorRequest,
  ConnectorListResponse,
  SingleConnectorResponse,
  ApiResponse,
} from "@/api/types/api.types";

const validateConnectorRequest = (data: any) => {
  if (!data) {
    throw new Error("Connector data is required");
  }
  // Add more validation as needed
};

const validateS3ConnectorRequest = (data: any) => {
  validateConnectorRequest(data);
  // Add S3-specific validation as needed
};

export const useGetS3Buckets = () => {
  const { showError } = useErrorModal();

  return useQuery<S3BucketResponse, Error>({
    queryKey: [QUERY_KEYS.CONNECTORS, "s3"],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<S3BucketResponse>(
          `${API_ENDPOINTS.CONNECTORS}/s3`,
          {
            signal,
          },
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch S3 buckets error:", error);
        showError("Failed to fetch S3 buckets");
        throw error;
      }
    },
  });
};

export const useGetConnectors = () => {
  const { showError } = useErrorModal();

  return useQuery<ConnectorListResponse, Error>({
    queryKey: [QUERY_KEYS.CONNECTORS],
    queryFn: async ({ signal }) => {
      try {
        const response = await apiClient.get<ConnectorListResponse>(
          API_ENDPOINTS.CONNECTORS,
          {
            signal,
          },
        );
        return response.data;
      } catch (error) {
        logger.error("Fetch connectors error:", error);
        showError("Failed to fetch connectors");
        throw error;
      }
    },
  });
};

export const useCreateConnector = () => {
  const { showError } = useErrorModal();

  return useMutation<ConnectorResponse, Error, CreateConnectorRequest>({
    mutationFn: async (data) => {
      validateConnectorRequest(data);
      const response = await apiClient.post<ConnectorResponse>(
        API_ENDPOINTS.CONNECTORS,
        data,
      );
      return response.data;
    },
    onError: (error) => {
      logger.error("Create connector error:", error);
      if (error.message === "Network Error") {
        showError("Unable to save connector - API is not available");
      } else {
        showError(`Failed to create connector: ${error.message}`);
      }
    },
    onSuccess: (newConnector) => {
      queryClient.setQueryData<ConnectorListResponse>(
        [QUERY_KEYS.CONNECTORS],
        (old) => {
          if (!old)
            return {
              status: "success",
              message: "Connectors retrieved successfully",
              data: { connectors: [newConnector] },
            };
          return {
            status: old.status,
            message: old.message,
            data: {
              ...old.data,
              connectors: [...old.data.connectors, newConnector],
            },
          };
        },
      );
    },
  });
};

export const useUpdateConnector = () => {
  const { showError } = useErrorModal();

  return useMutation<
    ConnectorResponse,
    Error,
    { id: string; data: UpdateConnectorRequest }
  >({
    mutationFn: async ({ id, data }) => {
      validateConnectorRequest(data);
      const response = await apiClient.put<ConnectorResponse>(
        `${API_ENDPOINTS.CONNECTORS}/${id}`,
        data,
      );
      return response.data;
    },
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: [QUERY_KEYS.CONNECTORS] });

      const previousConnectors =
        queryClient.getQueryData<ConnectorListResponse>([
          QUERY_KEYS.CONNECTORS,
        ]);

      queryClient.setQueryData<ConnectorListResponse>(
        [QUERY_KEYS.CONNECTORS],
        (old) => {
          if (!old) return previousConnectors;
          return {
            status: old.status,
            message: old.message,
            data: {
              ...old.data,
              connectors: old.data.connectors.map((connector) =>
                connector.id === id ? { ...connector, ...data } : connector,
              ),
            },
          };
        },
      );

      return { previousConnectors };
    },
    onError: (
      error,
      variables,
      context: { previousConnectors?: ConnectorListResponse },
    ) => {
      if (context?.previousConnectors) {
        queryClient.setQueryData(
          [QUERY_KEYS.CONNECTORS],
          context.previousConnectors,
        );
      }
      logger.error("Update connector error:", error);
      if (error.message === "Network Error") {
        showError("Unable to save connector - API is not available");
      } else {
        showError(`Failed to update connector: ${error.message}`);
      }
    },
  });
};

export const useToggleConnector = () => {
  const { showError } = useErrorModal();

  return useMutation<
    ConnectorResponse,
    Error,
    { id: string; enabled: boolean }
  >({
    mutationFn: async ({ id, enabled }) => {
      const response = await apiClient.put<ConnectorResponse>(
        `${API_ENDPOINTS.CONNECTORS}/${id}/status`,
        { status: enabled ? "active" : "disabled" },
      );
      return response.data;
    },
    onMutate: async ({ id, enabled }) => {
      await queryClient.cancelQueries({ queryKey: [QUERY_KEYS.CONNECTORS] });

      const previousConnectors =
        queryClient.getQueryData<ConnectorListResponse>([
          QUERY_KEYS.CONNECTORS,
        ]);

      queryClient.setQueryData<ConnectorListResponse>(
        [QUERY_KEYS.CONNECTORS],
        (old) => {
          if (!old) return previousConnectors;
          return {
            status: old.status,
            message: old.message,
            data: {
              ...old.data,
              connectors: old.data.connectors.map((connector) =>
                connector.id === id
                  ? { ...connector, status: enabled ? "active" : "disabled" }
                  : connector,
              ),
            },
          };
        },
      );

      return { previousConnectors };
    },
    onError: (
      error,
      variables,
      context: { previousConnectors?: ConnectorListResponse },
    ) => {
      if (context?.previousConnectors) {
        queryClient.setQueryData(
          [QUERY_KEYS.CONNECTORS],
          context.previousConnectors,
        );
      }
      logger.error("Toggle connector error:", error);
      showError(
        `Failed to ${variables.enabled ? "enable" : "disable"} connector`,
      );
    },
  });
};

export const useDeleteConnector = () => {
  const { showError } = useErrorModal();

  return useMutation({
    mutationFn: async (id: string) => {
      try {
        const response = await apiClient.delete<ApiResponse<void>>(
          `${API_ENDPOINTS.CONNECTORS}/${id}`,
        );
        return response.data;
      } catch (error) {
        logger.error("Delete connector error:", error);
        showError("Failed to delete connector");
        throw error;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.CONNECTORS] });
    },
  });
};

export const useCreateS3Connector = () => {
  const { showError } = useErrorModal();

  return useMutation<SingleConnectorResponse, any, CreateConnectorRequest>({
    mutationFn: async (data) => {
      validateS3ConnectorRequest(data);
      const response = await apiClient.post<SingleConnectorResponse>(
        `${API_ENDPOINTS.CONNECTORS}/s3`,
        data,
      );
      // Check if the response status is in the success range (200-299)
      if (response.status >= 200 && response.status < 300) {
        return response.data;
      } else {
        // If not successful, throw an error to trigger onError
        throw new Error(
          response.data.message || "Failed to create S3 connector",
        );
      }
    },
    onError: (error: any) => {
      logger.error("Create S3 connector error:", error);

      // Handle both axios error responses and thrown errors
      const errorMessage = error.response?.data?.body?.message || error.message;

      showError(`Failed to create S3 connector: ${errorMessage}`);
    },
    onSuccess: (response) => {
      if (Number(response.status) == 200) {
        const newConnector = response.data;

        // Merges the new connector into our existing connectors
        queryClient.setQueryData<ConnectorListResponse>(
          [QUERY_KEYS.CONNECTORS],
          (old) => {
            if (!old) {
              return {
                status: "success",
                message: "Connectors retrieved successfully",
                data: { connectors: [newConnector] },
              };
            }
            return {
              ...old,
              data: {
                ...old.data,
                connectors: [...old.data.connectors, newConnector],
              },
            };
          },
        );
      }
    },
  });
};

export const useCreateGCSConnector = () => {
  const { showError } = useErrorModal();

  return useMutation<ConnectorResponse, Error, CreateConnectorRequest>({
    mutationFn: async (data) => {
      const response = await apiClient.post<ConnectorResponse>(
        `${API_ENDPOINTS.CONNECTORS}/gcs`,
        data,
      );
      return response.data;
    },
    onError: (error) => {
      logger.error("Create GCS connector error:", error);
      if (error.message === "Network Error") {
        showError("Unable to save connector - API is not available");
      } else {
        showError(`Failed to create GCS connector: ${error.message}`);
      }
    },
  });
};

export const useSyncConnector = () => {
  const { showError } = useErrorModal();

  return useMutation<ApiResponse<any>, Error, string>({
    mutationFn: async (connectorId) => {
      try {
        const response = await apiClient.post<ApiResponse<any>>(
          `${API_ENDPOINTS.CONNECTORS}/${connectorId}/sync`,
        );
        return response.data;
      } catch (error) {
        logger.error("Sync connector error:", error);
        showError("Failed to sync connector");
        throw error;
      }
    },
    onSuccess: () => {
      // No need to invalidate queries as sync doesn't change connector data
      // but we might want to show a success message
    },
  });
};
