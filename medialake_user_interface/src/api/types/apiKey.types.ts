// src/api/types/apiKey.types.ts

export interface ApiKey {
  id: string;
  name: string;
  description: string;
  createdAt: string;
  updatedAt: string;
  isEnabled: boolean;
  lastUsed?: string;
}

export interface CreateApiKeyRequest {
  name: string;
  description: string;
  isEnabled?: boolean;
}

export interface UpdateApiKeyRequest {
  name?: string;
  description?: string;
  isEnabled?: boolean;
  rotateKey?: boolean;
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
