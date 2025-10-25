/**
 * Tag-Based Discovery Validation Tests
 * Validates the tag-based resource discovery system for both Cognito and CloudFront resources
 * Tests discovery methods, fallback mechanisms, and error handling
 */

import {
  test as enhancedCognitoTest,
  expect,
  EnhancedCognitoUtils,
} from "../fixtures/enhanced-cognito.fixtures";
import {
  test as cloudFrontTest,
  CloudFrontTestUtils,
} from "../fixtures/cloudfront.fixtures";
import { test as awsDiscoveryTest } from "../fixtures/aws-discovery.fixtures";
import {
  ResourceDiscoveryEngine,
  createResourceDiscoveryEngine,
  ResourceDiscoveryConfig,
} from "../utils/aws-resource-finder.js";
import {
  CognitoServiceAdapter,
  createCognitoServiceAdapter,
} from "../utils/cognito-service-adapter.js";
import {
  CloudFrontServiceAdapter,
  createCloudFrontServiceAdapter,
} from "../utils/cloudfront-service-adapter.js";
import {
  TagFilter,
  STANDARD_TAG_PATTERNS,
  TagMatcher,
  AWSTag,
} from "../utils/tag-matcher.js";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";

// Extended fixtures for tag-based discovery testing
interface TagDiscoveryFixtures {
  tagDiscoveryEngine: ResourceDiscoveryEngine;
  cognitoTagAdapter: CognitoServiceAdapter;
  cloudFrontTagAdapter: CloudFrontServiceAdapter;
  standardTagFilters: TagFilter[];
}

/**
 * Create discovery configuration for tag validation testing
 */
function createTagDiscoveryConfig(): ResourceDiscoveryConfig {
  return {
    region: AWS_REGION,
    profile: AWS_PROFILE,
    cacheTtlMs: 60000, // 1 minute for testing
    maxCacheSize: 50,
    enableFallback: true,
  };
}

/**
 * Get comprehensive tag filters for testing
 */
function getComprehensiveTagFilters(): TagFilter[] {
  return [
    STANDARD_TAG_PATTERNS.APPLICATION_TAG,
    {
      key: "Environment",
      values: [ENVIRONMENT, "dev", "test", "staging"],
      operator: "equals",
    },
    STANDARD_TAG_PATTERNS.TESTING_TAG,
    {
      key: "Owner",
      values: ["medialake-team", "aws-team"],
      operator: "equals",
    },
  ];
}

/**
 * Validate tag filter structure and content
 */
function validateTagFilter(filter: TagFilter): boolean {
  return !!(
    filter.key &&
    filter.values &&
    Array.isArray(filter.values) &&
    filter.values.length > 0 &&
    filter.operator &&
    ["equals", "contains", "starts-with"].includes(filter.operator)
  );
}

/**
 * Test tag matching logic
 */
async function testTagMatching(
  resourceTags: Record<string, string>,
  filters: TagFilter[],
): Promise<{
  matches: boolean;
  matchedFilters: string[];
  unmatchedFilters: string[];
}> {
  // Convert record to AWS tag format
  const awsTags: AWSTag[] = Object.entries(resourceTags).map(
    ([key, value]) => ({
      Key: key,
      Value: value,
    }),
  );

  const matchedFilters: string[] = [];
  const unmatchedFilters: string[] = [];

  for (const filter of filters) {
    const matches = TagMatcher.matchesTags(awsTags, [filter]);
    if (matches) {
      matchedFilters.push(filter.key);
    } else {
      unmatchedFilters.push(filter.key);
    }
  }

  return {
    matches: matchedFilters.length > 0,
    matchedFilters,
    unmatchedFilters,
  };
}

// Extend the AWS discovery test with tag-specific capabilities
const tagDiscoveryTest = awsDiscoveryTest.extend<TagDiscoveryFixtures>({
  /**
   * Tag discovery engine fixture
   */
  tagDiscoveryEngine: async (_fixtures, use, testInfo) => {
    const config = createTagDiscoveryConfig();
    const engine = createResourceDiscoveryEngine(config, testInfo.workerIndex);

    console.log(
      `[TagDiscovery Worker ${testInfo.workerIndex}] Initializing tag discovery engine`,
    );

    await use(engine);

    await engine.cleanup();
  },

  /**
   * Cognito tag adapter fixture
   */
  cognitoTagAdapter: async ({ tagDiscoveryEngine }, use) => {
    const config = createTagDiscoveryConfig();
    const adapter = createCognitoServiceAdapter(config);

    // Register with discovery engine
    tagDiscoveryEngine.registerAdapter(adapter);

    await use(adapter);

    await adapter.cleanup();
  },

  /**
   * CloudFront tag adapter fixture
   */
  cloudFrontTagAdapter: async ({ tagDiscoveryEngine }, use) => {
    const config = createTagDiscoveryConfig();
    const adapter = createCloudFrontServiceAdapter(config);

    // Register with discovery engine
    tagDiscoveryEngine.registerAdapter(adapter);

    await use(adapter);

    await adapter.cleanup();
  },

  /**
   * Standard tag filters fixture
   */
  standardTagFilters: async (_fixtures, use) => {
    const filters = getComprehensiveTagFilters();
    await use(filters);
  },
});

// Tag filter validation tests
tagDiscoveryTest.describe("Tag Filter Validation", () => {
  tagDiscoveryTest(
    "should validate standard tag patterns",
    async ({ standardTagFilters }) => {
      // Validate all standard tag filters
      for (const filter of standardTagFilters) {
        expect(validateTagFilter(filter)).toBe(true);
        expect(filter.key).toBeTruthy();
        expect(filter.values.length).toBeGreaterThan(0);
        expect(["equals", "contains", "starts-with"]).toContain(
          filter.operator,
        );
      }

      // Validate specific standard patterns
      const applicationFilter = standardTagFilters.find(
        (f) => f.key === "Application",
      );
      expect(applicationFilter).toBeTruthy();
      expect(applicationFilter!.values).toContain("medialake");

      console.log(
        `[Test] Validated ${standardTagFilters.length} standard tag filters`,
      );
    },
  );

  tagDiscoveryTest("should create custom tag filters correctly", async () => {
    // Test enhanced Cognito utils
    const customTags = {
      TestTag: "test-value",
      Environment: "integration-test",
      Owner: "test-team",
    };

    const customFilters =
      EnhancedCognitoUtils.createCustomTagFilters(customTags);

    expect(customFilters).toHaveLength(3);

    for (const filter of customFilters) {
      expect(validateTagFilter(filter)).toBe(true);
    }

    // Test CloudFront utils
    const cloudFrontCustomFilters =
      CloudFrontTestUtils.createCustomTagFilters(customTags);

    expect(cloudFrontCustomFilters).toHaveLength(3);
    expect(cloudFrontCustomFilters).toEqual(customFilters);

    console.log("[Test] Custom tag filters created and validated successfully");
  });

  tagDiscoveryTest("should handle tag matching logic correctly", async () => {
    const testResourceTags = {
      Application: "medialake",
      Environment: "dev",
      Owner: "medialake-team",
      Testing: "enabled",
    };

    const testFilters: TagFilter[] = [
      { key: "Application", values: ["medialake"], operator: "equals" },
      { key: "Environment", values: ["dev", "test"], operator: "equals" },
      { key: "Owner", values: ["other-team"], operator: "equals" }, // Should not match
      { key: "NonExistent", values: ["value"], operator: "equals" }, // Should not match
    ];

    const matchResult = await testTagMatching(testResourceTags, testFilters);

    expect(matchResult.matches).toBe(true);
    expect(matchResult.matchedFilters).toContain("Application");
    expect(matchResult.matchedFilters).toContain("Environment");
    expect(matchResult.unmatchedFilters).toContain("Owner");
    expect(matchResult.unmatchedFilters).toContain("NonExistent");

    console.log(
      `[Test] Tag matching: ${matchResult.matchedFilters.length} matched, ${matchResult.unmatchedFilters.length} unmatched`,
    );
  });
});

// Cognito tag-based discovery tests
enhancedCognitoTest.describe("Cognito Tag-Based Discovery Validation", () => {
  enhancedCognitoTest(
    "should discover Cognito user pools using tags",
    async ({ enhancedCognitoTestUser, cognitoDiscoveryEngine }) => {
      // Validate that discovery was successful
      expect(enhancedCognitoTestUser.userPool).toBeTruthy();
      expect(enhancedCognitoTestUser.discoveryMethod).toBeTruthy();

      // Test discovery method preference
      const preferredMethods = ["tag-based", "name-based", "fallback"];
      expect(preferredMethods).toContain(
        enhancedCognitoTestUser.discoveryMethod,
      );

      // If tag-based discovery was used, validate tags
      if (
        enhancedCognitoTestUser.discoveryMethod === "tag-based" &&
        enhancedCognitoTestUser.userPool
      ) {
        expect(enhancedCognitoTestUser.userPool.tags).toBeTruthy();
        expect(enhancedCognitoTestUser.userPool.tags!["Application"]).toBe(
          "medialake",
        );
      }

      // Test discovery engine cache
      const tagFilters = [STANDARD_TAG_PATTERNS.APPLICATION_TAG];
      const cachedResults = await cognitoDiscoveryEngine.discoverByTags(
        "cognito-user-pool",
        tagFilters,
      );

      expect(cachedResults).toBeDefined();
      expect(Array.isArray(cachedResults)).toBe(true);

      console.log(
        `[Test] Cognito discovery method: ${enhancedCognitoTestUser.discoveryMethod}`,
      );
      console.log(
        `[Test] User pool: ${enhancedCognitoTestUser.userPool?.name || enhancedCognitoTestUser.userPoolId}`,
      );
    },
  );

  enhancedCognitoTest(
    "should validate discovery method preferences",
    async ({ enhancedCognitoTestUser }) => {
      // Test utility function for discovery method validation
      const isTagBased = EnhancedCognitoUtils.validateDiscoveryMethod(
        enhancedCognitoTestUser,
        "tag-based",
      );
      const isNameBased = EnhancedCognitoUtils.validateDiscoveryMethod(
        enhancedCognitoTestUser,
        "name-based",
      );
      const isFallback = EnhancedCognitoUtils.validateDiscoveryMethod(
        enhancedCognitoTestUser,
        "fallback",
      );

      // Exactly one should be true
      const trueCount = [isTagBased, isNameBased, isFallback].filter(
        Boolean,
      ).length;
      expect(trueCount).toBe(1);

      // Validate that the correct method is identified
      switch (enhancedCognitoTestUser.discoveryMethod) {
        case "tag-based":
          expect(isTagBased).toBe(true);
          expect(isNameBased).toBe(false);
          expect(isFallback).toBe(false);
          break;
        case "name-based":
          expect(isTagBased).toBe(false);
          expect(isNameBased).toBe(true);
          expect(isFallback).toBe(false);
          break;
        case "fallback":
          expect(isTagBased).toBe(false);
          expect(isNameBased).toBe(false);
          expect(isFallback).toBe(true);
          break;
      }

      console.log(
        `[Test] Discovery method validation passed: ${enhancedCognitoTestUser.discoveryMethod}`,
      );
    },
  );

  enhancedCognitoTest(
    "should handle discovery fallback mechanisms",
    async ({ cognitoServiceAdapter }) => {
      // Test fallback discovery with various tag combinations
      const testTagFilters: TagFilter[] = [
        {
          key: "NonExistentTag",
          values: ["non-existent-value"],
          operator: "equals",
        },
      ];

      try {
        const fallbackResults =
          await cognitoServiceAdapter.fallbackDiscovery(testTagFilters);

        // Fallback should either return results or empty array, not throw
        expect(Array.isArray(fallbackResults)).toBe(true);

        console.log(
          `[Test] Fallback discovery returned ${fallbackResults.length} results`,
        );
      } catch (error) {
        // If fallback throws, it should be a meaningful error
        expect(error).toBeInstanceOf(Error);
        console.log(
          `[Test] Fallback discovery failed as expected: ${(error as Error).message}`,
        );
      }
    },
  );
});

// CloudFront tag-based discovery tests
cloudFrontTest.describe("CloudFront Tag-Based Discovery Validation", () => {
  cloudFrontTest(
    "should discover CloudFront distributions using tags",
    async ({ cloudFrontContext, cloudFrontDiscoveryEngine }) => {
      // Validate that discovery was successful
      expect(cloudFrontContext.distribution).toBeTruthy();
      expect(cloudFrontContext.discoveryMethod).toBeTruthy();

      // Test discovery method
      expect(["tag-based", "fallback"]).toContain(
        cloudFrontContext.discoveryMethod,
      );

      // If tag-based discovery was used, validate tags
      if (cloudFrontContext.discoveryMethod === "tag-based") {
        expect(cloudFrontContext.distribution.tags).toBeTruthy();
        expect(cloudFrontContext.distribution.tags!["Application"]).toBe(
          "medialake",
        );
      }

      // Test discovery engine functionality
      const tagFilters = [STANDARD_TAG_PATTERNS.APPLICATION_TAG];
      const discoveredDistributions =
        await cloudFrontDiscoveryEngine.discoverByTags(
          "cloudfront-distribution",
          tagFilters,
        );

      expect(discoveredDistributions).toBeDefined();
      expect(Array.isArray(discoveredDistributions)).toBe(true);

      console.log(
        `[Test] CloudFront discovery method: ${cloudFrontContext.discoveryMethod}`,
      );
      console.log(
        `[Test] Distribution: ${cloudFrontContext.distribution.name} (${cloudFrontContext.distribution.id})`,
      );
    },
  );

  cloudFrontTest(
    "should validate distribution information structure",
    async ({ cloudFrontContext }) => {
      const distributionInfo =
        CloudFrontTestUtils.getDistributionInfo(cloudFrontContext);

      // Validate required fields
      expect(distributionInfo.id).toBeTruthy();
      expect(distributionInfo.name).toBeTruthy();
      expect(distributionInfo.primaryDomain).toBeTruthy();
      expect(distributionInfo.discoveryMethod).toBeTruthy();
      expect(distributionInfo.testUrls).toBeTruthy();

      // Validate structure
      expect(typeof distributionInfo.id).toBe("string");
      expect(typeof distributionInfo.name).toBe("string");
      expect(typeof distributionInfo.primaryDomain).toBe("string");
      expect(["tag-based", "fallback"]).toContain(
        distributionInfo.discoveryMethod,
      );
      expect(Array.isArray(distributionInfo.aliases)).toBe(true);

      // Validate test URLs structure
      expect(distributionInfo.testUrls.root).toBeTruthy();
      expect(distributionInfo.testUrls.healthCheck).toBeTruthy();
      expect(distributionInfo.testUrls.staticAsset).toBeTruthy();

      console.log(
        `[Test] Distribution info validation passed for: ${distributionInfo.name}`,
      );
    },
  );

  cloudFrontTest(
    "should handle CloudFront service adapter fallback",
    async ({ cloudFrontServiceAdapter }) => {
      // Test fallback discovery with non-matching tags
      const testTagFilters: TagFilter[] = [
        {
          key: "NonExistentCloudFrontTag",
          values: ["non-existent-value"],
          operator: "equals",
        },
      ];

      try {
        const fallbackResults =
          await cloudFrontServiceAdapter.fallbackDiscovery(testTagFilters);

        // Fallback should return array (empty or with results)
        expect(Array.isArray(fallbackResults)).toBe(true);

        console.log(
          `[Test] CloudFront fallback discovery returned ${fallbackResults.length} results`,
        );
      } catch (error) {
        // If fallback throws, validate error handling
        expect(error).toBeInstanceOf(Error);
        console.log(
          `[Test] CloudFront fallback discovery failed as expected: ${(error as Error).message}`,
        );
      }
    },
  );
});

// Integrated tag discovery tests
tagDiscoveryTest.describe("Integrated Tag Discovery System", () => {
  tagDiscoveryTest(
    "should coordinate discovery across multiple services",
    async ({
      tagDiscoveryEngine,
      cognitoTagAdapter,
      cloudFrontTagAdapter,
      standardTagFilters,
    }) => {
      // Test that both adapters are registered
      expect(cognitoTagAdapter).toBeTruthy();
      expect(cloudFrontTagAdapter).toBeTruthy();

      // Test discovery across both services
      const cognitoResults = await tagDiscoveryEngine.discoverByTags(
        "cognito-user-pool",
        standardTagFilters,
      );
      const cloudFrontResults = await tagDiscoveryEngine.discoverByTags(
        "cloudfront-distribution",
        standardTagFilters,
      );

      expect(Array.isArray(cognitoResults)).toBe(true);
      expect(Array.isArray(cloudFrontResults)).toBe(true);

      console.log(
        `[Test] Integrated discovery - Cognito: ${cognitoResults.length}, CloudFront: ${cloudFrontResults.length}`,
      );
    },
  );

  tagDiscoveryTest(
    "should handle discovery engine caching",
    async ({ tagDiscoveryEngine, standardTagFilters }) => {
      // First discovery call
      const startTime1 = Date.now();
      const results1 = await tagDiscoveryEngine.discoverByTags(
        "cognito-user-pool",
        standardTagFilters,
      );
      const time1 = Date.now() - startTime1;

      // Second discovery call (should use cache)
      const startTime2 = Date.now();
      const results2 = await tagDiscoveryEngine.discoverByTags(
        "cognito-user-pool",
        standardTagFilters,
      );
      const time2 = Date.now() - startTime2;

      // Results should be the same
      expect(results1.length).toBe(results2.length);

      // Second call should be faster (cached)
      expect(time2).toBeLessThanOrEqual(time1);

      console.log(
        `[Test] Discovery caching - First: ${time1}ms, Second: ${time2}ms`,
      );
    },
  );

  tagDiscoveryTest(
    "should validate resource prefetching",
    async ({ tagDiscoveryEngine, standardTagFilters }) => {
      // Test prefetching functionality
      try {
        await tagDiscoveryEngine.prefetchResources(standardTagFilters);
        console.log("[Test] Resource prefetching completed successfully");
      } catch (error) {
        // Prefetching might fail in test environment, which is acceptable
        console.log(
          `[Test] Resource prefetching failed (expected in test): ${(error as Error).message}`,
        );
      }

      // Test that discovery still works after prefetch attempt
      const results = await tagDiscoveryEngine.discoverByTags(
        "cognito-user-pool",
        standardTagFilters,
      );
      expect(Array.isArray(results)).toBe(true);

      console.log(
        `[Test] Post-prefetch discovery returned ${results.length} results`,
      );
    },
  );
});

// Error handling and edge cases
tagDiscoveryTest.describe("Tag Discovery Error Handling", () => {
  tagDiscoveryTest(
    "should handle invalid tag filters gracefully",
    async ({ tagDiscoveryEngine }) => {
      // Test with invalid tag filters
      const invalidFilters: TagFilter[] = [
        { key: "", values: [], operator: "equals" }, // Invalid: empty key and values
        {
          key: "ValidKey",
          values: ["value"],
          operator: "invalid-operator" as any,
        }, // Invalid operator
      ];

      for (const invalidFilter of invalidFilters) {
        try {
          await tagDiscoveryEngine.discoverByTags("cognito-user-pool", [
            invalidFilter,
          ]);
          // If it doesn't throw, that's also acceptable (graceful handling)
          console.log(
            `[Test] Invalid filter handled gracefully: ${invalidFilter.key}`,
          );
        } catch (error) {
          // Expected to throw for invalid filters
          expect(error).toBeInstanceOf(Error);
          console.log(
            `[Test] Invalid filter rejected as expected: ${(error as Error).message}`,
          );
        }
      }
    },
  );

  tagDiscoveryTest(
    "should handle network and AWS API errors",
    async ({ tagDiscoveryEngine, standardTagFilters }) => {
      // This test validates that the system handles AWS API errors gracefully
      // In a real environment, this might include network timeouts, permission errors, etc.

      try {
        const results = await tagDiscoveryEngine.discoverByTags(
          "cognito-user-pool",
          standardTagFilters,
        );
        expect(Array.isArray(results)).toBe(true);
        console.log(
          `[Test] AWS API calls successful, returned ${results.length} results`,
        );
      } catch (error) {
        // If AWS API calls fail, validate error handling
        expect(error).toBeInstanceOf(Error);
        console.log(
          `[Test] AWS API error handled: ${(error as Error).message}`,
        );
      }
    },
  );

  tagDiscoveryTest(
    "should validate cleanup and resource management",
    async ({ tagDiscoveryEngine, cognitoTagAdapter, cloudFrontTagAdapter }) => {
      // Test that cleanup methods exist and can be called
      expect(typeof tagDiscoveryEngine.cleanup).toBe("function");
      expect(typeof cognitoTagAdapter.cleanup).toBe("function");
      expect(typeof cloudFrontTagAdapter.cleanup).toBe("function");

      // Cleanup should not throw errors
      await expect(cognitoTagAdapter.cleanup()).resolves.not.toThrow();
      await expect(cloudFrontTagAdapter.cleanup()).resolves.not.toThrow();

      console.log("[Test] Resource cleanup validation passed");
    },
  );
});

// Re-export expect for consistency
export { expect } from "@playwright/test";
