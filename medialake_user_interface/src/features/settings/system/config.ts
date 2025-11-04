export const SYSTEM_SETTINGS_CONFIG = {
  PROVIDERS: {
    TWELVE_LABS_API: {
      id: "twelvelabs-api",
      name: "TwelveLabs API",
      type: "twelvelabs",
      defaultEndpoint: "https://api.twelvelabs.io/v1",
      requiresApiKey: true,
    },
    TWELVE_LABS_BEDROCK: {
      id: "twelvelabs-bedrock",
      name: "TwelveLabs Bedrock",
      type: "twelvelabs-bedrock",
      requiresApiKey: false,
    },
    COACTIVE: {
      id: "coactive",
      name: "Coactive AI",
      type: "coactive",
      defaultEndpoint: "https://app.coactive.ai/api/v1/search",
      requiresApiKey: true,
    },
  },
  EMBEDDING_STORES: {
    OPENSEARCH: {
      id: "opensearch",
      name: "OpenSearch",
    },
    S3_VECTOR: {
      id: "s3-vector",
      name: "S3 Vectors",
    },
  },
  DEFAULT_PROVIDER: "twelvelabs-api",
  DEFAULT_EMBEDDING_STORE: "opensearch",
};
