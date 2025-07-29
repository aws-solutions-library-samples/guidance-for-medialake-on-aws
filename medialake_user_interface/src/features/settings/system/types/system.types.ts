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
  embeddingStore?: {
    type: "opensearch" | "s3-vector";
    isEnabled?: boolean;
    config?: object;
  };
}

export interface EmbeddingStore {
  type: "opensearch" | "s3-vector";
  isEnabled: boolean;
  config?: {
    opensearchEndpoint?: string;
    s3Bucket?: string;
    indexName?: string;
  };
  createdAt?: string;
  updatedAt?: string;
}

export interface SearchProviderUpdate {
  name?: string;
  apiKey?: string;
  endpoint?: string;
  isEnabled?: boolean;
  embeddingStore?: {
    type: "opensearch" | "s3-vector";
    isEnabled?: boolean;
    config?: object;
  };
}

// New types for the three-part settings structure
export interface SemanticSearchSettings {
  isEnabled: boolean;
  provider: {
    type: "twelvelabs-api" | "twelvelabs-bedrock";
    config: SearchProvider | null;
  };
  embeddingStore: {
    type: "opensearch" | "s3-vector";
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
    embeddingStore?: EmbeddingStore;
  };
}

export interface SystemSettingsError {
  status?: number;
  message: string;
}
