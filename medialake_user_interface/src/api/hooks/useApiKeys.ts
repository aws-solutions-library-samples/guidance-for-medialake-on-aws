import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";
import {
  ApiKey,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  UpdateApiKeyPermissionsRequest,
  UpdateApiKeyPermissionsResponse,
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
  return useQuery<ApiKey[], Error>({
    queryKey: QUERY_KEYS.API_KEYS.all,
    enabled: enabled,
    queryFn: async ({ signal }) => {
      try {
        const { data } = await apiClient.get<any>(API_ENDPOINTS.API_KEYS.BASE, {
          signal,
        });

        // Use robust parser to handle all response formats
        const apiKeys = parseApiKeysList(data);
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
      const { data } = await apiClient.get<ApiKeyListResponse>(
        // const { data } = await apiClient.get<any>(
        API_ENDPOINTS.API_KEYS.GET(id),
        { signal }
      );

      // Use robust parser to handle all response formats
      const apiKey = parseApiKey(data);
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

export const useUpdateApiKeyPermissions = () => {
  const queryClient = useQueryClient();

  return useMutation<
    UpdateApiKeyPermissionsResponse,
    Error,
    { id: string; request: UpdateApiKeyPermissionsRequest }
  >({
    mutationFn: async ({ id, request }) => {
      const { data } = await apiClient.put<{
        statusCode: number;
        body: string;
      }>(API_ENDPOINTS.API_KEYS.PERMISSIONS(id), request);
      return parseStringBodyResponse<UpdateApiKeyPermissionsResponse>(data);
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
