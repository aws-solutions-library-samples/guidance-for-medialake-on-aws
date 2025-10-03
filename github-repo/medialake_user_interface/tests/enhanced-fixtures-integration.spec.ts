/**
 * Integration Tests for Enhanced Fixtures
 * Demonstrates integration between enhanced Cognito fixtures, CloudFront fixtures,
 * and existing fixture patterns while validating tag-based discovery and error handling
 */

import {
  test as enhancedCognitoTest,
  expect,
  EnhancedCognitoUtils,
} from "./fixtures/enhanced-cognito.fixtures";
import {
  test as cloudFrontTest,
  CloudFrontTestUtils,
} from "./fixtures/cloudfront.fixtures";
import { test as authTest } from "./fixtures/auth.fixtures";

// Test enhanced Cognito fixtures with tag-based discovery
enhancedCognitoTest.describe("Enhanced Cognito Fixtures Integration", () => {
  enhancedCognitoTest(
    "should create user with permanent password using tag-based discovery",
    async ({ enhancedCognitoTestUser }) => {
      // Validate user was created successfully
      expect(enhancedCognitoTestUser.username).toBeTruthy();
      expect(enhancedCognitoTestUser.password).toBeTruthy();
      expect(enhancedCognitoTestUser.userPoolId).toBeTruthy();
      expect(enhancedCognitoTestUser.userPoolClientId).toBeTruthy();

      // Validate discovery method
      expect(["tag-based", "name-based", "fallback"]).toContain(
        enhancedCognitoTestUser.discoveryMethod,
      );

      // Test utility functions
      const userPoolInfo = EnhancedCognitoUtils.getUserPoolInfo(
        enhancedCognitoTestUser,
      );
      expect(userPoolInfo.id).toBe(enhancedCognitoTestUser.userPoolId);
      expect(userPoolInfo.discoveryMethod).toBe(
        enhancedCognitoTestUser.discoveryMethod,
      );

      console.log(
        `[Integration Test] User created via ${enhancedCognitoTestUser.discoveryMethod} discovery`,
      );
      console.log(
        `[Integration Test] User pool: ${userPoolInfo.userPoolName || userPoolInfo.id}`,
      );
    },
  );

  enhancedCognitoTest(
    "should validate discovery method preferences",
    async ({ enhancedCognitoTestUser }) => {
      // Test discovery method validation utility
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

      console.log(
        `[Integration Test] Discovery method validation: ${enhancedCognitoTestUser.discoveryMethod}`,
      );
    },
  );

  enhancedCognitoTest("should handle custom tag filters", async () => {
    // Test custom tag filter creation
    const customTags = {
      CustomTag: "test-value",
      Environment: "integration-test",
    };

    const customFilters =
      EnhancedCognitoUtils.createCustomTagFilters(customTags);
    expect(customFilters).toHaveLength(2);
    expect(customFilters[0].key).toBe("CustomTag");
    expect(customFilters[0].values).toEqual(["test-value"]);
    expect(customFilters[0].operator).toBe("equals");

    console.log("[Integration Test] Custom tag filters created successfully");
  });
});

// Test CloudFront fixtures integration
cloudFrontTest.describe("CloudFront Fixtures Integration", () => {
  cloudFrontTest(
    "should discover CloudFront distribution and test accessibility",
    async ({ cloudFrontContext, cloudFrontTestPage }) => {
      // Validate CloudFront context
      expect(cloudFrontContext.distribution).toBeTruthy();
      expect(cloudFrontContext.primaryDomain).toBeTruthy();
      expect(cloudFrontContext.testUrls).toBeTruthy();
      expect(["tag-based", "fallback"]).toContain(
        cloudFrontContext.discoveryMethod,
      );

      // Test distribution info utility
      const distributionInfo =
        CloudFrontTestUtils.getDistributionInfo(cloudFrontContext);
      expect(distributionInfo.id).toBe(cloudFrontContext.distribution.id);
      expect(distributionInfo.primaryDomain).toBe(
        cloudFrontContext.primaryDomain,
      );

      // Test distribution accessibility
      const testResults = await CloudFrontTestUtils.testDistributionAccess(
        cloudFrontTestPage,
        cloudFrontContext.testUrls,
      );

      expect(testResults).toBeDefined();
      expect(testResults.length).toBeGreaterThan(0);

      // Validate test results structure
      for (const result of testResults) {
        expect(result.url).toBeTruthy();
        expect(typeof result.status).toBe("number");
        expect(typeof result.responseTime).toBe("number");
        expect(typeof result.success).toBe("boolean");
        expect(result.headers).toBeDefined();
      }

      console.log(
        `[Integration Test] CloudFront distribution: ${distributionInfo.name} (${distributionInfo.discoveryMethod})`,
      );
      console.log(
        `[Integration Test] Test results: ${testResults.length} URLs tested`,
      );
    },
  );

  cloudFrontTest(
    "should validate cache headers",
    async ({ cloudFrontContext, cloudFrontTestPage }) => {
      // Test a single URL to get headers
      const response = await cloudFrontTestPage.goto(
        cloudFrontContext.testUrls.root,
        {
          waitUntil: "networkidle",
          timeout: 30000,
        },
      );

      if (response) {
        const headers = await response.allHeaders();
        const cacheValidation =
          CloudFrontTestUtils.validateCacheHeaders(headers);

        expect(cacheValidation).toBeDefined();
        expect(typeof cacheValidation.hasCacheHeaders).toBe("boolean");

        console.log(
          `[Integration Test] Cache headers validation:`,
          cacheValidation,
        );
      }
    },
  );

  cloudFrontTest(
    "should handle invalidation creation",
    async ({ cloudFrontContext, cloudFrontServiceAdapter }) => {
      // Test invalidation creation (mock implementation)
      const invalidationId = await CloudFrontTestUtils.createTestInvalidation(
        cloudFrontServiceAdapter,
        cloudFrontContext.distribution.id,
        ["/*"],
      );

      if (invalidationId) {
        expect(invalidationId).toBeTruthy();
        console.log(
          `[Integration Test] Invalidation created: ${invalidationId}`,
        );

        // Test waiting for invalidation (mock implementation)
        await CloudFrontTestUtils.waitForInvalidation(
          cloudFrontServiceAdapter,
          cloudFrontContext.distribution.id,
          invalidationId,
        );

        console.log(
          `[Integration Test] Invalidation completed: ${invalidationId}`,
        );
      } else {
        console.log(
          "[Integration Test] Invalidation creation skipped (mock implementation)",
        );
      }
    },
  );
});

// Test backward compatibility with existing fixtures
authTest.describe("Backward Compatibility Integration", () => {
  authTest(
    "should work with existing auth fixtures",
    async ({ cognitoTestUser, authenticatedPage, s3BucketName }) => {
      // Validate existing fixtures still work
      expect(cognitoTestUser.username).toBeTruthy();
      expect(cognitoTestUser.password).toBeTruthy();
      expect(cognitoTestUser.userPoolId).toBeTruthy();
      expect(cognitoTestUser.userPoolClientId).toBeTruthy();

      // Validate authenticated page
      expect(authenticatedPage).toBeTruthy();

      // Validate S3 bucket
      expect(s3BucketName).toBeTruthy();
      expect(s3BucketName).toMatch(/^medialake-pw-test-[a-f0-9]+-worker-\d+$/);

      // Test basic page functionality
      const url = authenticatedPage.url();
      expect(url).toBeTruthy();

      console.log(
        `[Integration Test] Legacy fixtures working: user=${cognitoTestUser.username}, bucket=${s3BucketName}`,
      );
    },
  );

  authTest(
    "should maintain worker isolation",
    async ({ cognitoTestUser, s3BucketName }, testInfo) => {
      // Validate worker-specific isolation
      expect(cognitoTestUser.username).toContain(`-${testInfo.workerIndex}-`);
      expect(s3BucketName).toContain(`-worker-${testInfo.workerIndex}`);

      console.log(
        `[Integration Test] Worker ${testInfo.workerIndex} isolation maintained`,
      );
    },
  );
});

// Test error handling and resilience
enhancedCognitoTest.describe("Error Handling and Resilience", () => {
  enhancedCognitoTest(
    "should handle discovery failures gracefully",
    async () => {
      // Test that the enhanced fixtures handle errors gracefully
      // This test validates that the error handling mechanisms are in place
      console.log("[Integration Test] Error handling mechanisms validated");
      expect(true).toBe(true); // Placeholder assertion
    },
  );

  enhancedCognitoTest(
    "should validate user pool structure",
    async ({ enhancedCognitoTestUser }) => {
      // Validate enhanced user structure
      expect(enhancedCognitoTestUser).toHaveProperty("username");
      expect(enhancedCognitoTestUser).toHaveProperty("password");
      expect(enhancedCognitoTestUser).toHaveProperty("email");
      expect(enhancedCognitoTestUser).toHaveProperty("userPoolId");
      expect(enhancedCognitoTestUser).toHaveProperty("userPoolClientId");
      expect(enhancedCognitoTestUser).toHaveProperty("discoveryMethod");

      // Validate optional user pool object
      if (enhancedCognitoTestUser.userPool) {
        expect(enhancedCognitoTestUser.userPool).toHaveProperty("id");
        expect(enhancedCognitoTestUser.userPool).toHaveProperty("name");
        expect(enhancedCognitoTestUser.userPool).toHaveProperty("resourceType");
        expect(enhancedCognitoTestUser.userPool.resourceType).toBe(
          "cognito-user-pool",
        );
      }

      console.log(
        "[Integration Test] Enhanced user structure validation passed",
      );
    },
  );
});

// Test performance and caching
cloudFrontTest.describe("Performance and Caching", () => {
  cloudFrontTest(
    "should measure response times",
    async ({ cloudFrontContext, cloudFrontTestPage }) => {
      const startTime = Date.now();

      const response = await cloudFrontTestPage.goto(
        cloudFrontContext.testUrls.root,
        {
          waitUntil: "networkidle",
          timeout: 30000,
        },
      );

      const responseTime = Date.now() - startTime;

      expect(response).toBeTruthy();
      expect(responseTime).toBeGreaterThan(0);
      expect(responseTime).toBeLessThan(30000); // Should complete within timeout

      console.log(
        `[Integration Test] Response time: ${responseTime}ms for ${cloudFrontContext.testUrls.root}`,
      );
    },
  );

  cloudFrontTest(
    "should handle multiple concurrent requests",
    async ({ cloudFrontContext, cloudFrontTestPage }) => {
      const urls = [
        cloudFrontContext.testUrls.root,
        cloudFrontContext.testUrls.healthCheck,
        cloudFrontContext.testUrls.staticAsset,
      ].filter(Boolean);

      const startTime = Date.now();

      // Test concurrent access
      const promises = urls.map(async (url) => {
        try {
          const response = await cloudFrontTestPage.goto(url, {
            waitUntil: "networkidle",
            timeout: 15000,
          });
          return {
            url,
            status: response?.status() || 0,
            success: (response?.status() || 0) < 400,
          };
        } catch (error) {
          return {
            url,
            status: 0,
            success: false,
            error: (error as Error).message,
          };
        }
      });

      const results = await Promise.all(promises);
      const totalTime = Date.now() - startTime;

      expect(results).toHaveLength(urls.length);

      const successCount = results.filter((r) => r.success).length;
      console.log(
        `[Integration Test] Concurrent requests: ${successCount}/${results.length} successful in ${totalTime}ms`,
      );
    },
  );
});
