export interface SearchProvider {
  id?: string;
  name: string;
  type: string;
  apiKey: string;
  endpoint?: string;
  isConfigured?: boolean;
  isEnabled?: boolean;
  isExternal?: boolean;
  supportedMediaTypes?: string[];
  dimensions?: number;
  createdAt?: string;
  updatedAt?: string;
  // Coactive advanced configuration
  searchEndpoint?: string;
  datasetEndpoint?: string;
  authEndpoint?: string;
  responseFormat?: string;
  datasetId?: string;
}

export interface SearchProviderCreate {
  name: string;
  type: string;
  apiKey: string;
  endpoint?: string;
  isEnabled?: boolean;
  dimensions?: number;
  embeddingStore?: {
    type: "opensearch" | "s3-vector";
    isEnabled?: boolean;
    config?: object;
  };
  // Coactive advanced configuration
  searchEndpoint?: string;
  datasetEndpoint?: string;
  authEndpoint?: string;
  responseFormat?: string;
  datasetId?: string;
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

export interface ProviderMetadata {
  id: string;
  name: string;
  type: string;
  defaultEndpoint?: string;
  requiresApiKey: boolean;
  isExternal: boolean;
  supportedMediaTypes: string[];
  dimensions?: number[];
  // Coactive advanced endpoint defaults
  defaultSearchEndpoint?: string;
  defaultDatasetEndpoint?: string;
  defaultAuthEndpoint?: string;
  defaultResponseFormat?: string;
  supportedResponseFormats?: string[];
}

export interface EmbeddingStoreMetadata {
  id: string;
  name: string;
}

export interface SearchProviderUpdate {
  name?: string;
  type?: string;
  apiKey?: string;
  endpoint?: string;
  isEnabled?: boolean;
  dimensions?: number;
  embeddingStore?: {
    type: "opensearch" | "s3-vector";
    isEnabled?: boolean;
    config?: object;
  };
  // Coactive advanced configuration
  searchEndpoint?: string;
  datasetEndpoint?: string;
  authEndpoint?: string;
  responseFormat?: string;
  datasetId?: string;
}

// New types for the three-part settings structure
export interface SemanticSearchSettings {
  isEnabled: boolean;
  provider: {
    type: "none" | "twelvelabs-api" | "twelvelabs-bedrock" | "twelvelabs-bedrock-3-0" | "coactive";
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
    availableProviders?: Record<string, ProviderMetadata>;
    availableEmbeddingStores?: Record<string, EmbeddingStoreMetadata>;
  };
}

export interface SystemSettingsError {
  status?: number;
  message: string;
}
