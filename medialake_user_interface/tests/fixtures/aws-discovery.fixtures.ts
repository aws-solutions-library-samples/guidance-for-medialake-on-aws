/**
 * AWS Resource Discovery Fixtures
 * Provides unified tag-based resource discovery for Playwright tests
 * Integrates with existing fixture patterns while adding new capabilities
 */

import { test as base } from "@playwright/test";
import {
  ResourceDiscoveryEngine,
  createResourceDiscoveryEngine,
  ResourceDiscoveryConfig,
} from "../utils/aws-resource-finder.js";
import {
  CognitoServiceAdapter,
  createCognitoServiceAdapter,
  CognitoUserPool,
} from "../utils/cognito-service-adapter.js";
import {
  CloudFrontServiceAdapter,
  createCloudFrontServiceAdapter,
  CloudFrontDistribution,
} from "../utils/cloudfront-service-adapter.js";
import { TagFilter, STANDARD_TAG_PATTERNS } from "../utils/tag-matcher.js";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";

// Types for AWS discovery fixtures
export interface AWSResourceContext {
  cognitoUserPool?: CognitoUserPool;
  cloudFrontDistribution?: CloudFrontDistribution;
  discoveryEngine: ResourceDiscoveryEngine;
  environment: string;
  region: string;
}

export interface AWSDiscoveryFixtures {
  awsResourceContext: AWSResourceContext;
  cognitoDiscovery: CognitoServiceAdapter;
  cloudFrontDiscovery: CloudFrontServiceAdapter;
  discoveryEngine: ResourceDiscoveryEngine;
}

/**
 * Create discovery configuration from environment
 */
function createDiscoveryConfig(): ResourceDiscoveryConfig {
  return {
    region: AWS_REGION,
    profile: AWS_PROFILE,
    cacheTtlMs: 300000, // 5 minutes
    maxCacheSize: 100,
    enableFallback: true,
  };
}

/**
 * Get standard tag filters for the current environment
 */
function getEnvironmentTagFilters(): TagFilter[] {
  return [
    STANDARD_TAG_PATTERNS.APPLICATION_TAG,
    {
      key: "Environment",
      values: [ENVIRONMENT],
      operator: "equals",
    },
    STANDARD_TAG_PATTERNS.TESTING_TAG,
  ];
}

// Extend the base Playwright test with AWS discovery fixtures
export const test = base.extend<AWSDiscoveryFixtures>({
  /**
   * Discovery engine fixture - test scoped for proper Playwright integration
   */
  discoveryEngine: async ({}, use, testInfo) => {
    const config = createDiscoveryConfig();
    const engine = createResourceDiscoveryEngine(config, testInfo.workerIndex);

    console.log(
      `[AWSDiscovery Worker ${testInfo.workerIndex}] Initializing discovery engine`,
    );

    // Register service adapters
    const cognitoAdapter = createCognitoServiceAdapter(config);
    const cloudFrontAdapter = createCloudFrontServiceAdapter(config);

    engine.registerAdapter(cognitoAdapter);
    engine.registerAdapter(cloudFrontAdapter);

    // Prefetch common resources
    try {
      const commonFilters = getEnvironmentTagFilters();
      await engine.prefetchResources(commonFilters);
    } catch (error) {
      console.warn(
        `[AWSDiscovery Worker ${testInfo.workerIndex}] Prefetch failed:`,
        error,
      );
    }

    await use(engine);

    // Cleanup
    await engine.cleanup();
  },

  /**
   * Cognito discovery service adapter
   */
  cognitoDiscovery: async ({}, use) => {
    const config = createDiscoveryConfig();
    const adapter = createCognitoServiceAdapter(config);

    await use(adapter);

    await adapter.cleanup();
  },

  /**
   * CloudFront discovery service adapter
   */
  cloudFrontDiscovery: async ({}, use) => {
    const config = createDiscoveryConfig();
    const adapter = createCloudFrontServiceAdapter(config);

    await use(adapter);

    await adapter.cleanup();
  },

  /**
   * Unified AWS resource context with discovered resources
   */
  awsResourceContext: [
    async ({ discoveryEngine }, use, testInfo) => {
      console.log(
        `[AWSDiscovery Test ${testInfo.title}] Setting up resource context`,
      );

      const tagFilters = getEnvironmentTagFilters();
      let cognitoUserPool: CognitoUserPool | undefined;
      let cloudFrontDistribution: CloudFrontDistribution | undefined;

      try {
        // Discover Cognito user pool
        const cognitoPools = await discoveryEngine.discoverByTags(
          "cognito-user-pool",
          tagFilters,
        );
        if (cognitoPools.length > 0) {
          cognitoUserPool = cognitoPools[0] as CognitoUserPool;
          console.log(
            `[AWSDiscovery] Found Cognito user pool: ${cognitoUserPool.name} (${cognitoUserPool.id})`,
          );
        } else {
          console.warn(
            `[AWSDiscovery] No Cognito user pools found with tags:`,
            tagFilters,
          );
        }

        // Discover CloudFront distribution
        const distributions = await discoveryEngine.discoverByTags(
          "cloudfront-distribution",
          tagFilters,
        );
        if (distributions.length > 0) {
          cloudFrontDistribution = distributions[0] as CloudFrontDistribution;
          console.log(
            `[AWSDiscovery] Found CloudFront distribution: ${cloudFrontDistribution.name} (${cloudFrontDistribution.id})`,
          );
        } else {
          console.warn(
            `[AWSDiscovery] No CloudFront distributions found with tags:`,
            tagFilters,
          );
        }
      } catch (error) {
        console.error(`[AWSDiscovery] Error during resource discovery:`, error);
      }

      const context: AWSResourceContext = {
        cognitoUserPool,
        cloudFrontDistribution,
        discoveryEngine,
        environment: ENVIRONMENT,
        region: AWS_REGION,
      };

      await use(context);

      console.log(
        `[AWSDiscovery Test ${testInfo.title}] Resource context cleanup completed`,
      );
    },
    { scope: "test" },
  ],
});

/**
 * Enhanced test user creation with discovered resources
 */
export interface EnhancedCognitoTestUser {
  username: string;
  password: string;
  email: string;
  userPoolId: string;
  userPoolClientId: string;
  userPool: CognitoUserPool;
}

/**
 * Extended test with enhanced Cognito user creation
 */
export const testWithEnhancedCognito = test.extend<{
  enhancedCognitoTestUser: EnhancedCognitoTestUser;
}>({
  enhancedCognitoTestUser: [
    async ({ awsResourceContext, cognitoDiscovery }, use, testInfo) => {
      if (!awsResourceContext.cognitoUserPool) {
        throw new Error(
          "No Cognito user pool found for enhanced test user creation",
        );
      }

      const userPool = awsResourceContext.cognitoUserPool;
      const randomId = Math.random().toString(36).substring(2, 8);
      const uniqueEmail = `mne-medialake+e2etest-${testInfo.workerIndex}-${randomId}@amazon.com`;

      console.log(
        `[EnhancedCognito] Creating test user in pool: ${userPool.name}`,
      );

      // Get password policy and generate appropriate password
      const passwordPolicy = await cognitoDiscovery.getUserPoolPasswordPolicy(
        userPool.id,
      );
      const password = generateSecurePassword(passwordPolicy?.PasswordPolicy);

      // Create the test user
      await cognitoDiscovery.createTestUser(
        userPool.id,
        uniqueEmail,
        password,
        uniqueEmail,
      );

      const testUser: EnhancedCognitoTestUser = {
        username: uniqueEmail,
        password,
        email: uniqueEmail,
        userPoolId: userPool.id,
        userPoolClientId: userPool.clients[0]?.id || "",
        userPool,
      };

      await use(testUser);

      // Cleanup: Delete the test user
      try {
        await cognitoDiscovery.deleteTestUser(userPool.id, uniqueEmail);
      } catch (cleanupError) {
        console.error(
          "[EnhancedCognito] Error during user cleanup:",
          cleanupError,
        );
      }
    },
    { scope: "test" },
  ],
});

/**
 * Generate secure password based on policy requirements
 */
function generateSecurePassword(passwordPolicy?: any): string {
  const minLength = passwordPolicy?.MinimumLength || 20;
  const requireUppercase = passwordPolicy?.RequireUppercase !== false;
  const requireLowercase = passwordPolicy?.RequireLowercase !== false;
  const requireNumbers = passwordPolicy?.RequireNumbers !== false;
  const requireSymbols = passwordPolicy?.RequireSymbols !== false;

  const uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lowercase = "abcdefghijklmnopqrstuvwxyz";
  const numbers = "0123456789";
  const symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?";

  let password = "";
  let availableChars = "";

  // Add required character types
  if (requireUppercase) {
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    availableChars += uppercase;
  }

  if (requireLowercase) {
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    availableChars += lowercase;
  }

  if (requireNumbers) {
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    availableChars += numbers;
  }

  if (requireSymbols) {
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
    availableChars += symbols;
  }

  // If no specific requirements, use all character types
  if (!availableChars) {
    availableChars = uppercase + lowercase + numbers + symbols;
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
  }

  // Fill to minimum length
  while (password.length < minLength) {
    password += availableChars.charAt(
      Math.floor(Math.random() * availableChars.length),
    );
  }

  // Shuffle the password to randomize character positions
  return password
    .split("")
    .sort(() => Math.random() - 0.5)
    .join("");
}

/**
 * Utility functions for tests
 */
export const AWSDiscoveryUtils = {
  /**
   * Create custom tag filters for specific test scenarios
   */
  createCustomTagFilters(customTags: Record<string, string>): TagFilter[] {
    return Object.entries(customTags).map(([key, value]) => ({
      key,
      values: [value],
      operator: "equals" as const,
    }));
  },

  /**
   * Get discovery engine statistics for debugging
   */
  async getDiscoveryStats(engine: ResourceDiscoveryEngine): Promise<any> {
    return engine.getStats();
  },

  /**
   * Invalidate discovery cache for fresh resource lookup
   */
  async invalidateCache(
    engine: ResourceDiscoveryEngine,
    resourceType?: string,
  ): Promise<void> {
    engine.invalidateCache(resourceType as any);
  },
};

// Re-export expect from the base playwright test module
export { expect } from "@playwright/test";
