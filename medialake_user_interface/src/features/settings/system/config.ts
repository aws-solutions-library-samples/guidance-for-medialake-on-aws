export const SYSTEM_SETTINGS_CONFIG = {
  PROVIDERS: {
    TWELVE_LABS_API: {
      id: "twelvelabs-api",
      name: "TwelveLabs Marengo Embed 2.7 API",
      type: "twelvelabs",
      defaultEndpoint: "https://api.twelvelabs.io/v1",
      requiresApiKey: true,
      dimensions: [1024],
    },
    TWELVE_LABS_BEDROCK: {
      id: "twelvelabs-bedrock",
      name: "TwelveLabs Marengo Embed 2.7 on Bedrock",
      type: "twelvelabs-bedrock",
      requiresApiKey: false,
      dimensions: [1024],
    },
    TWELVE_LABS_BEDROCK_3_0: {
      id: "twelvelabs-bedrock-3-0",
      name: "TwelveLabs Marengo Embed 3.0 on Bedrock",
      type: "twelvelabs-bedrock-3-0",
      requiresApiKey: false,
      dimensions: [512],
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
