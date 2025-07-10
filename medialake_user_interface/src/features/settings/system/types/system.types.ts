export interface SearchProvider {
  id?: string;
  name: string;
  type: string;
  apiKey: string;
  endpoint?: string;
  isConfigured?: boolean;
  isEnabled?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface SearchProviderCreate {
  name: string;
  type: string;
  apiKey: string;
  endpoint?: string;
  isEnabled?: boolean;
}

export interface SearchProviderUpdate {
  name?: string;
  apiKey?: string;
  endpoint?: string;
  isEnabled?: boolean;
}

export interface SystemSettingsResponse {
  status: string;
  message: string;
  data: {
    searchProvider?: SearchProvider;
  };
}

export interface SystemSettingsError {
  status?: number;
  message: string;
} 