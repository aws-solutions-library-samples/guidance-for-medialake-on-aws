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

// New types for the three-part settings structure
export interface SemanticSearchSettings {
  isEnabled: boolean;
  provider: {
    type: 'twelvelabs-api' | 'twelvelabs-bedrock';
    config: SearchProvider | null;
  };
  embeddingStore: {
    type: 'opensearch' | 's3-vector';
  };
}

export interface SystemSettingsState {
  current: SemanticSearchSettings;
  original: SemanticSearchSettings;
  hasChanges: boolean;
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