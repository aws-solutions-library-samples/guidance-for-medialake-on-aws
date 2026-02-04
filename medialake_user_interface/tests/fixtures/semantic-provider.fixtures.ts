/**
 * Semantic Provider Fixtures for Playwright Tests
 *
 * Provides test-scoped provider configuration and cleanup fixtures
 * for semantic search E2E tests.
 *
 * @requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5
 *
 * **Feature: twelvelabs-marengo-3-0-playwright-tests**
 */

import { test as authTest } from "./auth.fixtures";
import { Page, TestInfo } from "@playwright/test";
import {
  ProviderConfigHelper,
  ProviderConfig,
  EmbeddingStoreConfig,
  ProviderType,
  EmbeddingStoreType,
  PROVIDER_METADATA,
} from "../utils/provider-config-helper";
import { TestConfiguration, TEST_CONFIGURATIONS } from "../utils/test-config-models";

/**
 * Semantic provider fixture types
 */
export type SemanticProviderFixtures = {
  /** Provider configuration extracted from test info */
  providerConfig: ProviderConfig;
  /** Embedding store configuration */
  embeddingStoreConfig: EmbeddingStoreConfig;
  /** Side effect fixture that configures provider before test */
  configuredProvider: void;
  /** Cleanup function for provider reset */
  providerCleanup: () => Promise<void>;
  /** Test configuration for current test */
  testConfiguration: TestConfiguration | null;
  /** Provider config helper instance */
  providerHelper: ProviderConfigHelper;
};

/**
 * Extract provider configuration from test info annotations or title
 *
 * Parses test title or annotations to determine which provider/store
 * combination should be used for the test.
 */
function extractProviderConfigFromTest(testInfo: TestInfo): ProviderConfig {
  const title = testInfo.title.toLowerCase();
  const annotations = testInfo.annotations;

  // Check annotations first
  const providerAnnotation = annotations.find((a) => a.type === "provider");
  if (providerAnnotation && providerAnnotation.description) {
    const providerType = providerAnnotation.description as ProviderType;
    const metadata = PROVIDER_METADATA[providerType];
    if (metadata) {
      return {
        type: providerType,
        name: metadata.displayName,
        dimensions: metadata.dimensions,
        apiKey: metadata.requiresApiKey ? process.env[metadata.apiKeyEnvVar || ""] : undefined,
      };
    }
  }

  // Parse from test title
  let providerType: ProviderType = "twelvelabs-bedrock"; // Default

  if (title.includes("twelvelabs") && title.includes("api")) {
    providerType = "twelvelabs-api";
  } else if (title.includes("twelvelabs") && title.includes("3.0")) {
    providerType = "twelvelabs-bedrock-3-0";
  } else if (title.includes("twelvelabs") && title.includes("bedrock")) {
    providerType = "twelvelabs-bedrock";
  } else if (title.includes("coactive")) {
    providerType = "coactive";
  }

  const metadata = PROVIDER_METADATA[providerType];
  return {
    type: providerType,
    name: metadata.displayName,
    dimensions: metadata.dimensions,
    apiKey: metadata.requiresApiKey ? process.env[metadata.apiKeyEnvVar || ""] : undefined,
  };
}

/**
 * Extract embedding store configuration from test info
 */
function extractEmbeddingStoreConfigFromTest(
  testInfo: TestInfo,
  providerType: ProviderType
): EmbeddingStoreConfig {
  const title = testInfo.title.toLowerCase();
  const annotations = testInfo.annotations;

  // Check annotations first
  const storeAnnotation = annotations.find((a) => a.type === "embeddingStore");
  if (storeAnnotation && storeAnnotation.description) {
    return {
      type: storeAnnotation.description as EmbeddingStoreType,
      isEnabled: true,
    };
  }

  // External providers use native storage
  const metadata = PROVIDER_METADATA[providerType];
  if (metadata.isExternal) {
    return {
      type: "native",
      isEnabled: true,
    };
  }

  // Parse from test title for internal providers
  if (title.includes("s3") || title.includes("s3-vector")) {
    return {
      type: "s3-vector",
      isEnabled: true,
    };
  }

  // Default to OpenSearch for internal providers
  return {
    type: "opensearch",
    isEnabled: true,
  };
}

/**
 * Get test configuration by provider and store type
 */
function getTestConfigurationForTest(
  providerType: ProviderType,
  storeType: EmbeddingStoreType
): TestConfiguration | null {
  return (
    TEST_CONFIGURATIONS.find(
      (config) => config.provider.type === providerType && config.embeddingStore.type === storeType
    ) || null
  );
}

/**
 * Check if API key is available for a provider
 */
export function isApiKeyAvailable(providerType: ProviderType): boolean {
  const metadata = PROVIDER_METADATA[providerType];
  if (!metadata.requiresApiKey) {
    return true; // No API key required
  }
  const apiKey = process.env[metadata.apiKeyEnvVar || ""];
  return !!apiKey && apiKey.length > 0;
}

/**
 * Get API key for a provider from environment variables
 */
export function getApiKeyForProvider(providerType: ProviderType): string | undefined {
  const metadata = PROVIDER_METADATA[providerType];
  if (!metadata.requiresApiKey) {
    return undefined;
  }
  return process.env[metadata.apiKeyEnvVar || ""];
}

/**
 * Extended test fixture with semantic provider capabilities
 */
export const test = authTest.extend<SemanticProviderFixtures>({
  /**
   * Provider configuration fixture
   * Extracts provider config from test title or annotations
   */
  providerConfig: async ({}, use, testInfo) => {
    const config = extractProviderConfigFromTest(testInfo);
    console.log(`[SemanticProviderFixture] Provider config: ${config.type} (${config.name})`);
    await use(config);
  },

  /**
   * Embedding store configuration fixture
   */
  embeddingStoreConfig: async ({ providerConfig }, use, testInfo) => {
    const config = extractEmbeddingStoreConfigFromTest(testInfo, providerConfig.type);
    console.log(`[SemanticProviderFixture] Embedding store config: ${config.type}`);
    await use(config);
  },

  /**
   * Test configuration fixture
   * Provides the full test configuration for the current provider/store combination
   */
  testConfiguration: async ({ providerConfig, embeddingStoreConfig }, use) => {
    const config = getTestConfigurationForTest(providerConfig.type, embeddingStoreConfig.type);
    console.log(`[SemanticProviderFixture] Test configuration: ${config ? "found" : "not found"}`);
    await use(config);
  },

  /**
   * Provider config helper instance
   */
  providerHelper: async ({ authenticatedPage }, use) => {
    const helper = new ProviderConfigHelper(authenticatedPage);
    await use(helper);
  },

  /**
   * Configured provider fixture
   * Sets up the provider before test and cleans up after
   */
  configuredProvider: async (
    { authenticatedPage, providerConfig, embeddingStoreConfig, providerHelper },
    use
  ) => {
    console.log(`[SemanticProviderFixture] Setting up provider: ${providerConfig.type}`);

    // Check if API key is required and available
    const metadata = PROVIDER_METADATA[providerConfig.type];
    if (metadata.requiresApiKey && !providerConfig.apiKey) {
      console.log(
        `[SemanticProviderFixture] Skipping provider setup - API key not available for ${providerConfig.type}`
      );
      await use();
      return;
    }

    try {
      // Navigate to System Settings
      await providerHelper.navigateToSystemSettings();

      // Select and configure the provider
      await providerHelper.selectProvider(providerConfig.type);
      await providerHelper.configureProvider(providerConfig);

      // Select embedding store for internal providers
      if (!metadata.isExternal) {
        await providerHelper.selectEmbeddingStore(embeddingStoreConfig);
      }

      // Save configuration
      await providerHelper.saveConfiguration();

      console.log(`[SemanticProviderFixture] Provider configured: ${providerConfig.type}`);
    } catch (error) {
      console.error(`[SemanticProviderFixture] Error configuring provider: ${error}`);
      // Don't throw - let the test handle the error
    }

    // Use the configured provider
    await use();

    // Cleanup after test
    console.log(`[SemanticProviderFixture] Cleaning up provider: ${providerConfig.type}`);
    try {
      await providerHelper.resetProvider();
    } catch (error) {
      console.error(`[SemanticProviderFixture] Error resetting provider: ${error}`);
    }
  },

  /**
   * Provider cleanup function
   * Can be called manually if needed
   */
  providerCleanup: async ({ providerHelper }, use) => {
    const cleanup = async () => {
      console.log("[SemanticProviderFixture] Manual cleanup requested");
      try {
        await providerHelper.resetProvider();
        console.log("[SemanticProviderFixture] Provider reset successfully");
      } catch (error) {
        console.error(`[SemanticProviderFixture] Error during cleanup: ${error}`);
      }
    };

    await use(cleanup);
  },
});

// Re-export expect from Playwright
export { expect } from "@playwright/test";

// Re-export types for convenience
export type { ProviderConfig, EmbeddingStoreConfig, ProviderType, EmbeddingStoreType };
export { PROVIDER_METADATA };
