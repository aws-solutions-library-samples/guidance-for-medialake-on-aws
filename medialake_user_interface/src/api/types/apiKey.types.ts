// src/api/types/apiKey.types.ts

/** Flat permission map using resource:action format */
export type ApiKeyPermissions = Record<string, boolean>;

/** Scope presets available during API key creation */
export type ApiKeyScope = "read-only" | "read-write" | "admin" | "custom"; // pragma: allowlist secret

export interface ApiKey {
  id: string;
  name: string;
  description: string;
  createdAt: string;
  updatedAt: string;
  isEnabled: boolean;
  lastUsed?: string;
  permissions?: ApiKeyPermissions;
  scope?: ApiKeyScope;
}

export interface CreateApiKeyRequest {
  name: string;
  description: string;
  isEnabled?: boolean;
  scope?: ApiKeyScope;
  permissions?: ApiKeyPermissions;
}

export interface UpdateApiKeyRequest {
  name?: string;
  description?: string;
  isEnabled?: boolean;
  rotateKey?: boolean;
  permissions?: ApiKeyPermissions;
}

export interface UpdateApiKeyPermissionsRequest {
  permissions: ApiKeyPermissions;
  mode?: "merge" | "replace";
}

export interface UpdateApiKeyPermissionsResponse {
  status: string;
  message: string;
  data: {
    id: string;
    permissions: ApiKeyPermissions;
    mode: string;
    updatedAt: string;
  };
}

export interface ApiKeyListResponse {
  status: string;
  message: string;
  data: {
    apiKeys: ApiKey[];
  };
}

export interface ApiKeyResponse {
  status: string;
  message: string;
  data: ApiKey;
}

export interface CreateApiKeyResponse {
  status: string;
  message: string;
  data: ApiKey & {
    apiKey: string; // The full API key string (id_secret)
  };
}

export interface RotateApiKeyResponse {
  status: string;
  message: string;
  data: ApiKey & {
    apiKey: string; // The full API key string (id_secret)
  };
}
