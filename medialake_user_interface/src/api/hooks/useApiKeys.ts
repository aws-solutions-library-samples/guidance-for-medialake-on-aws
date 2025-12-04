import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  ApiKey,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  ApiKeyListResponse,
  ApiKeyResponse,
  CreateApiKeyResponse,
  RotateApiKeyResponse,
} from "../types/apiKey.types";
import {
  parseApiKeysList,
  parseApiKey,
  parseStringBodyResponse,
  handleApiKeysError,
} from "../utils/responseParser";

export const useGetApiKeys = (enabled = false) => {
  // Add a unique identifier to track each hook instance
  const hookId = React.useId();
  console.log(`useGetApiKeys hook instance created: ${hookId}`);

  return useQuery<ApiKey[], Error>({
    queryKey: QUERY_KEYS.API_KEYS.all,
    enabled: enabled,
    queryFn: async ({ signal }) => {
      try {
        console.log(
          `Fetching API keys... [${new Date().toISOString()}] from hook instance: ${hookId}`
        );
        const { data } = await apiClient.get<any>(API_ENDPOINTS.API_KEYS.BASE, {
          signal,
        });
        console.log(
          `API keys API response [${new Date().toISOString()}] for hook instance: ${hookId}`
        );

        // Use robust parser to handle all response formats
        const apiKeys = parseApiKeysList(data);
        console.log(`Parsed ${apiKeys.length} API keys for hook instance: ${hookId}`);
        return apiKeys;
      } catch (error: any) {
        // Use centralized error handling for 403 errors
        return handleApiKeysError(error);
      }
    },
  });
};

export const useGetApiKey = (id: string, enabled = true) => {
  return useQuery<ApiKey, Error>({
    queryKey: QUERY_KEYS.API_KEYS.detail(id),
    enabled: enabled && !!id,
    queryFn: async ({ signal }) => {
      console.log(`Fetching API key with id: ${id}`);
      const { data } = await apiClient.get<ApiKeyListResponse>(
        // const { data } = await apiClient.get<any>(
        API_ENDPOINTS.API_KEYS.GET(id),
        { signal }
      );
      console.log("API key API response:", data);

      // Use robust parser to handle all response formats
      const apiKey = parseApiKey(data);
      console.log("Parsed API key:", apiKey);
      return apiKey;
    },
  });
};

export const useCreateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateApiKeyResponse, Error, CreateApiKeyRequest>({
    mutationFn: async (apiKeyData) => {
      const { data } = await apiClient.post<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.API_KEYS.BASE, apiKeyData);
      return parseStringBodyResponse<CreateApiKeyResponse>(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.API_KEYS.all,
      });
    },
  });
};

export const useUpdateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<
    ApiKeyResponse | RotateApiKeyResponse,
    Error,
    { id: string; updates: UpdateApiKeyRequest }
  >({
    mutationFn: async ({ id, updates }) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.API_KEYS.UPDATE(id), updates);
      return parseStringBodyResponse<ApiKeyResponse | RotateApiKeyResponse>(data);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.API_KEYS.all,
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.API_KEYS.detail(variables.id),
      });
    },
  });
};

export const useDeleteApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (apiKeyId) => {
      await apiClient.delete(API_ENDPOINTS.API_KEYS.DELETE(apiKeyId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.API_KEYS.all,
      });
    },
  });
};

export const useRotateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<RotateApiKeyResponse, Error, string>({
    mutationFn: async (apiKeyId) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.API_KEYS.UPDATE(apiKeyId), { rotateKey: true });
      return parseStringBodyResponse<RotateApiKeyResponse>(data);
    },
    onSuccess: (_, apiKeyId) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.API_KEYS.all,
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.API_KEYS.detail(apiKeyId),
      });
    },
  });
};
