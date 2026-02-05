/**
 * Test Configuration Models for Semantic Search E2E Tests
 *
 * Defines TypeScript interfaces for test configuration, provider metadata,
 * search results, and clip data models.
 *
 * @requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
 */

import { ProviderType, EmbeddingStoreType } from "./provider-config-helper";

/**
 * Test configuration for a single provider/store combination
 */
export interface TestConfiguration {
  provider: {
    type: ProviderType;
    name: string;
    dimensions: number;
    requiresApiKey: boolean;
    apiKeyEnvVar?: string;
  };
  embeddingStore: {
    type: EmbeddingStoreType;
    isEnabled: boolean;
  };
  testData: {
    videoFile: string;
    searchQuery: string;
    expectedClipCount: number;
  };
}

/**
 * Provider metadata model
 */
export interface ProviderMetadata {
  id: string;
  name: string;
  type: string;
  dimensions: number[];
  requiresApiKey: boolean;
  isExternal: boolean;
  supportedMediaTypes: string[];
  inferenceProvider: string;
}

/**
 * Search result data model
 */
export interface SearchResultData {
  hits: SearchHit[];
  totalResults: number;
  maxScore: number;
  tookMs: number;
  provider: string;
  architectureType: string;
}

/**
 * Individual search hit
 */
export interface SearchHit {
  assetId: string;
  score: number;
  source: Record<string, unknown>;
  mediaType: "video" | "image" | "audio";
  clips?: ClipData[];
}

/**
 * Clip data model
 */
export interface ClipData {
  timestamp: number;
  confidence: number;
  duration?: number;
  embeddingType: string;
}

/**
 * Search result interface for helper classes
 */
export interface SearchResult {
  assetId: string;
  score: number;
  clips: Clip[];
}

/**
 * Clip interface for helper classes
 */
export interface Clip {
  timestamp: number;
  confidence: number;
  duration?: number;
}

/**
 * Clip validation result
 */
export interface ClipValidationResult {
  clipsFound: boolean;
  clipCount: number;
  clipsMatchThreshold: boolean;
  timelineMarkersVisible: boolean;
}

/**
 * Pipeline deployment result
 */
export interface PipelineDeploymentResult {
  success: boolean;
  pipelineIds: string[];
  error?: string;
}

/**
 * All test configurations for the 7 provider/store combinations
 */
export const TEST_CONFIGURATIONS: TestConfiguration[] = [
  {
    provider: {
      type: "twelvelabs-api",
      name: "TwelveLabs Marengo 2.7 API",
      dimensions: 1024,
      requiresApiKey: true,
      apiKeyEnvVar: "TWELVELABS_API_KEY", // pragma: allowlist secret
    },
    embeddingStore: {
      type: "opensearch",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
  {
    provider: {
      type: "twelvelabs-api",
      name: "TwelveLabs Marengo 2.7 API",
      dimensions: 1024,
      requiresApiKey: true,
      apiKeyEnvVar: "TWELVELABS_API_KEY", // pragma: allowlist secret
    },
    embeddingStore: {
      type: "s3-vector",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
  {
    provider: {
      type: "twelvelabs-bedrock",
      name: "TwelveLabs Marengo 2.7 Bedrock",
      dimensions: 1024,
      requiresApiKey: false,
    },
    embeddingStore: {
      type: "opensearch",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
  {
    provider: {
      type: "twelvelabs-bedrock",
      name: "TwelveLabs Marengo 2.7 Bedrock",
      dimensions: 1024,
      requiresApiKey: false,
    },
    embeddingStore: {
      type: "s3-vector",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
  {
    provider: {
      type: "twelvelabs-bedrock-3-0",
      name: "TwelveLabs Marengo 3.0 Bedrock",
      dimensions: 512,
      requiresApiKey: false,
    },
    embeddingStore: {
      type: "opensearch",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
  {
    provider: {
      type: "twelvelabs-bedrock-3-0",
      name: "TwelveLabs Marengo 3.0 Bedrock",
      dimensions: 512,
      requiresApiKey: false,
    },
    embeddingStore: {
      type: "s3-vector",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
  {
    provider: {
      type: "coactive",
      name: "Coactive AI",
      dimensions: 1024,
      requiresApiKey: true,
      apiKeyEnvVar: "COACTIVE_API_KEY", // pragma: allowlist secret
    },
    embeddingStore: {
      type: "native",
      isEnabled: true,
    },
    testData: {
      videoFile: "test-video.mp4",
      searchQuery: "person walking",
      expectedClipCount: 1,
    },
  },
];

/**
 * Get test configuration by provider type and store type
 */
export function getTestConfiguration(
  providerType: ProviderType,
  storeType: EmbeddingStoreType
): TestConfiguration | undefined {
  return TEST_CONFIGURATIONS.find(
    (config) => config.provider.type === providerType && config.embeddingStore.type === storeType
  );
}

/**
 * Get all test configurations for a specific provider type
 */
export function getConfigurationsForProvider(providerType: ProviderType): TestConfiguration[] {
  return TEST_CONFIGURATIONS.filter((config) => config.provider.type === providerType);
}

/**
 * Check if a provider requires an API key
 */
export function providerRequiresApiKey(providerType: ProviderType): boolean {
  const config = TEST_CONFIGURATIONS.find((c) => c.provider.type === providerType);
  return config?.provider.requiresApiKey ?? false;
}

/**
 * Get the API key environment variable name for a provider
 */
export function getApiKeyEnvVar(providerType: ProviderType): string | undefined {
  const config = TEST_CONFIGURATIONS.find((c) => c.provider.type === providerType);
  return config?.provider.apiKeyEnvVar;
}

/**
 * Get the expected dimensions for a provider
 */
export function getProviderDimensions(providerType: ProviderType): number {
  const config = TEST_CONFIGURATIONS.find((c) => c.provider.type === providerType);
  return config?.provider.dimensions ?? 1024;
}
